# Copyright 2019 StackHPC Ltd.
# Copyright 2017-2018 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import math
import re
from collections import defaultdict

import monasca_agent.collector.checks as checks
from prometheus_client.parser import text_string_to_metric_families
import requests
import yaml


class MetricStore(object):
    def __init__(self, whitelist=None, label_whitelist=None):
        self.metrics = defaultdict(lambda: defaultdict(list))
        # This whitelist is a list of regexes hence why we don't use a set
        self.whitelist_regex = ('(?:' + ')|(?:'.join(whitelist) + ')'
                                if whitelist else None)
        self.label_whitelist = (set(label_whitelist)
                                if label_whitelist else None)

    def add_sample(self, name, metric_type, value, labels={}):
        sample = {'labels': labels, 'value': value}
        self.metrics[name]['samples'].append(sample)

        # Let this be set once and error if it doesn't match?
        self.metrics[name]['type'] = metric_type

    def get_samples(self, name):
        return self.metrics.get(name, {}).get('samples', {})

    def get_type(self, name):
        metric = self.metrics.get(name)
        return metric['type'] if metric else None

    def set_type(self, name, metric_type):
        metric = self.metrics.get(name)
        if metric:
            metric['type'] = metric_type

    def get_metrics_by_type(self, metric_type):
        return {
            k: v for k, v in self.metrics.items() if v['type'] == metric_type}

    def get_metrics(self):
        metrics_list = []
        for metric_name, metric in self.metrics.items():
            if self.whitelist_regex and not re.match(
                    self.whitelist_regex, metric_name):
                # Filter out metric
                continue
            for sample in metric.get('samples'):
                # Filter labels
                if self.label_whitelist:
                    labels = {k: v for k, v in sample['labels'].items(
                    ) if k in self.label_whitelist}
                else:
                    labels = sample['labels']
                metric = {'name': metric_name,
                          'value': sample['value'],
                          'dimensions': labels,
                          'type': metric['type']}
                metrics_list.append(metric)
        return metrics_list


class PrometheusV2(checks.AgentCheck):
    """Scrapes metrics from Prometheus endpoints
    """

    def __init__(self, name, init_config, agent_config, instances=None):
        super(PrometheusV2, self).__init__(
            name, init_config, agent_config, instances)
        self.connection_timeout = init_config.get("timeout", 3)

    def check(self, instance):
        dimensions = self._set_dimensions(None, instance)
        if instance.get("remove_hostname"):
            del dimensions['hostname']
        dimensions.update(instance.get("default_dimensions", {}))

        if not instance.get("metric_endpoint"):
            self.log.error("metric_endpoint must be defined for each instance")
            return

        derived_metrics = instance.get("derived_metrics")
        if derived_metrics and isinstance(derived_metrics, str):
            instance['derived_metrics'] = yaml.safe_load(derived_metrics)
        # TODO: Validate it looks sane
        # TODO: validate whitelist, convert counter to rates option
        # TODO: member var instance

        try:
            result = requests.get(instance['metric_endpoint'],
                                  timeout=self.connection_timeout)
        except Exception as e:
            self.log.error(
                "Could not get metrics from {} with error {}".format(
                    instance['metric_endpoint'], e))
        else:
            result_content_type = result.headers['Content-Type']
            if "text/plain" in result_content_type:
                try:
                    # Note that due to the OpenMetrics standard, this
                    # appends `_total` to all counters.
                    metric_families = text_string_to_metric_families(
                        result.text)
                    self._send_metrics(metric_families,
                                       dimensions,
                                       instance)
                except Exception as e:
                    self.log.error(
                        "Error parsing data from {} with error {}".format(
                            instance['metric_endpoint'], e))
            else:
                self.log.error(
                    "Unsupported content type - {}".format(
                        result_content_type))

    def _send_metrics(self, metric_families, dimensions, instance):
        metrics = MetricStore(whitelist=instance.get('whitelist'),
                              label_whitelist=instance.get('label_whitelist'))
        self._parse_metrics(metrics, metric_families)
        self._compute_derived_metrics(metrics, instance)
        self._write_out_metrics(metrics, dimensions, instance)

    def _parse_metrics(self, metric_store, metric_families):
        """Load metrics into a store which can be queried later"""
        for metric_family in metric_families:
            for metric in metric_family.samples:
                metric_name = metric[0]
                metric_labels = metric[1]
                metric_value = float(metric[2])

                if PrometheusV2._skip_metric(metric_value):
                    self.log.debug(
                        'Filtered out metric with NaN value %s{%s}',
                        metric_name,
                        metric_labels)
                    continue

                metric_dimensions = PrometheusV2._labels_to_dimensions(
                    metric_labels)
                metric_store.add_sample(metric_name,
                                        metric_family.type,
                                        metric_value,
                                        metric_dimensions)

    @staticmethod
    def _skip_metric(metric_value):
        return True if math.isnan(metric_value) else False

    @staticmethod
    def _labels_to_dimensions(labels):
        # TODO: Check if we could create invalid dimensions from the labels
        return {k: v for k, v in labels.items() if len(v) > 0}

    def _lookup_metric_type(self, metric_name, metrics):
        metric_type = metrics.get_type(metric_name)
        if not metric_type:
            self.log.warning("Could not look up type for metric {}. Does "
                             "the metric exist?".format(metric_name))
            return
        return metric_type

    def _compute_derived_metrics(self, metrics, instance):
        """Create new metrics from operations on existing metrics"""
        derived_metrics = instance.get('derived_metrics', {})
        for derived_metric_name, conf in derived_metrics.items():
            # Assume derived metrics config has already been checked so
            # we don't need to check it again here
            if conf['op'] == 'divide':
                self._divide_metric_pairs(derived_metric_name, conf, metrics)
            elif conf['op'] == 'sum':
                self._sum_metric_series(derived_metric_name, conf, metrics)
            elif conf['op'] == 'counter':
                self._metric_series_to_counter(
                    derived_metric_name, conf, metrics)
            else:
                self.log.warning(
                    "Skipping derived metric: {}, operation not "
                    "supported: {}.".format(derived_metric_name, conf['op']))

    def _metric_series_to_counter(self, derived_metric_name, conf, metrics):
        """ Create a new counter metric from an existing metric.

            Useful for mislabelled counters and taking derivatives of
            non-counters. Eg. rate of change of used space on Ceph cluster."""
        if derived_metric_name == conf['series']:
            # Mark the raw series directly as a 'counter' type rather than
            # deriving a new series from it.
            metrics.set_type(derived_metric_name, 'counter')
            return

        samples = metrics.get_samples(conf['series'])
        if not samples:
            return

        # Create a new series of 'counter' type from the raw series.
        for sample in samples:
            metrics.add_sample(derived_metric_name, 'counter',
                               sample['value'], sample['labels'])

    def _sum_metric_series(self, derived_metric_name, conf, metrics):
        samples = metrics.get_samples(conf['series'])
        if not samples:
            return

        # TODO: Assert there are samples
        series_type = self._lookup_metric_type(conf['series'], metrics)

        filtered_samples = {}
        sum_measurement = {'value': 0.0, 'labels': {}}
        first_label_hash = None
        for sample in samples:
            # Don't mess with the existing sample since we may want to send it
            sample_labels = copy.deepcopy(sample.get('labels'))
            if not sample_labels:
                self.log.warning("Sample has no dimensions, skipping.")
                continue
            key = sample_labels.pop(conf['key'])
            # Return if there is more than one measurement for the specified
            # key
            if filtered_samples.get(key):
                self.log.warning("Sample with matching key detected {}."
                                 "Skipping derived metric: {}."
                                 .format(conf['key'], derived_metric_name))
                return
            # Make sure that all other labels are the same
            if not first_label_hash:
                first_label_hash = hash(str(sample_labels))
            else:
                if hash(str(sample_labels)) != first_label_hash:
                    self.log.warning("Sample dimensions are not all fixed "
                                     "with respect to the specified key {}. "
                                     "Skipping derived metric: {}.".format(
                                         conf['key'], derived_metric_name))
                    return
            # Key the samples by the specified dimension key so that we
            # can detect duplicate keys, and ensure remaining dimensions
            # are all the same.
            filtered_samples[key] = True
            # Labels should all be the same so we only set it once
            if not sum_measurement.get('labels') and sample_labels:
                sum_measurement['labels'].update(sample_labels)
            sum_measurement['value'] = sum_measurement['value'] + \
                sample['value']

        metrics.add_sample(derived_metric_name, series_type,
                           sum_measurement['value'], sum_measurement['labels'])

    def _divide_metric_pairs(self, derived_metric_name, conf, metrics):
        x_type = self._lookup_metric_type(conf['x'], metrics)
        y_type = self._lookup_metric_type(conf['y'], metrics)
        if not x_type or not y_type:
            return

        if x_type != y_type:
            self.log.warning(
                "Skipping derived metric: {}. Types {} and {} do not match.".
                format(derived_metric_name, x_type, y_type))
            return

        # Hash the dimensions so that we can match up metrics
        # Eg. When calculating OSD fractional utilisation from
        # space used and total space, you need to ensure that those
        # metrics come from the same OSD. We may want to introduce
        # a configurable key to match on at a later date. Eg. osd
        # dimension.
        # TODO: Fail if we get hash collisions (e.g.
        # multiple metrics with no labels)
        x_metrics = PrometheusV2._hash_metrics(
            metrics.get_samples(conf['x']))
        y_metrics = PrometheusV2._hash_metrics(
            metrics.get_samples(conf['y']))

        # Create derived metric
        for metric_hash in x_metrics.keys():
            value = x_metrics[metric_hash]['value'] / \
                y_metrics[metric_hash]['value']
            metrics.add_sample(derived_metric_name, x_type,
                               value, x_metrics[metric_hash]['labels'])

    # Move to metrics store
    @staticmethod
    def _hash_metrics(metrics):
        hashed_metrics = {}
        for metric in metrics:
            hashed_metrics[hash(str(metric['labels']))] = metric
        return hashed_metrics

    def _write_out_metrics(self, metrics, dimensions, instance):
        counters_to_rates = instance.get('counters_to_rates', True)
        for metric in metrics.get_metrics():
            metric['dimensions'].update(dimensions)
            metric_func = self._get_metric_func(metric, counters_to_rates)
            self._write_metric(metric_func,
                               metric['name'],
                               metric['value'],
                               dimensions=metric['dimensions'])

    def _get_metric_func(self, metric, counters_to_rates):
        if counters_to_rates and (
                metric['type'] == 'counter' or (
                metric['name'].endswith('_total'))):
            metric_func = self.rate
            metric['name'] += "_rate"
        else:
            metric_func = self.gauge
        return metric_func

    def _write_metric(self, metric_func, name, value, dimensions):
        metric_func(name, value, dimensions)
