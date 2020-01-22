# Copyright 2019 StackHPC Ltd.
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

import os
import unittest

import mock

import stackhpc_monasca_agent_plugins.checks.prometheusv2 as prometheus


class MockPrometheusPlugin(prometheus.PrometheusV2):
    def __init__(self):
        # Don't call the base class constructor
        pass
        self.connection_timeout = 1
        self.log = mock.Mock()

    def _set_dimensions(self, dimensions, instance=None):
        # Cut down version of original, which doesn't get actual
        # hostname or try to read config file
        new_dimensions = {}
        new_dimensions.update({'hostname': 'squawky'})
        if dimensions is not None:
            new_dimensions.update(dimensions)
        if instance:
            new_dimensions.update(instance.get('dimensions', {}))
        return new_dimensions


class TestPrometheus(unittest.TestCase):
    def setUp(self):
        filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'example_prometheus_ceph_metrics')
        with open(filepath, 'r') as f:
            self.example_scrape_output = f.read()
        self.prometheus = MockPrometheusPlugin()

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_check_derived_metric(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': True,
            'derived_metrics': 'ceph_cluster_usage:\n   x: ceph_cluster_total_used_bytes\n   y: ceph_cluster_total_bytes\n   opp: divide\n   type: gauge\n',  # noqa
            'default_dimensions': {'ceph': 'app'}
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_usage',
                      0.2097226390639752,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'})
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_derived_counter_metric(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': True,
            'derived_metrics': 'ceph_cluster_total_used_bytes_total:\n   series: ceph_cluster_total_used_bytes\n   opp: counter\n',  # noqa
            'default_dimensions': {'ceph': 'app'}
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes_total_rate',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_derived_counter_metric_autoconvert_total(
            self, mock_write_metric, mock_req):
        # HAProxy exporter has some metrics which are counters and end in
        # _total, but are labelled as gauges. Here we check the autoconversion
        # of those to counters.
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'remove_hostname': True
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}

        filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'example_prometheus_haproxy_metrics')
        with open(filepath, 'r') as f:
            example_scrape_output = f.read()
        mock_req.return_value.text = example_scrape_output

        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'haproxy_backend_http_total_time_average_seconds',
                      0.0,
                      dimensions={'backend': 'cinder_api'}),
            mock.call(mock.ANY,
                      'haproxy_backend_http_total_time_average_seconds',
                      0.944,
                      dimensions={'backend': 'elasticsearch'}),
            mock.call(mock.ANY,
                      'haproxy_server_downtime_seconds_total_rate',
                      0.0,
                      dimensions={'backend': 'cinder_api',
                                  'server': 'foo'}),
            mock.call(mock.ANY,
                      'haproxy_server_downtime_seconds_total_rate',
                      0.0,
                      dimensions={'backend': 'elasticsearch',
                                  'server': 'bar'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_derived_counter_metric_autoconvert_total_disabled(
            self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': False,
            'remove_hostname': True
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}

        filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'example_prometheus_haproxy_metrics')
        with open(filepath, 'r') as f:
            example_scrape_output = f.read()
        mock_req.return_value.text = example_scrape_output

        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'haproxy_backend_http_total_time_average_seconds',
                      0.0,
                      dimensions={'backend': 'cinder_api'}),
            mock.call(mock.ANY,
                      'haproxy_backend_http_total_time_average_seconds',
                      0.944,
                      dimensions={'backend': 'elasticsearch'}),
            mock.call(mock.ANY,
                      'haproxy_server_downtime_seconds_total',
                      0.0,
                      dimensions={'backend': 'cinder_api',
                                  'server': 'foo'}),
            mock.call(mock.ANY,
                      'haproxy_server_downtime_seconds_total',
                      0.0,
                      dimensions={'backend': 'elasticsearch',
                                  'server': 'bar'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_derived_counter_metric_same_name(
            self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': True,
             # Change the metric type from a gauge to a counter so that it
             # gets converted to a rate 'in place' and without creating a
             # new series.
            'derived_metrics': 'ceph_cluster_total_used_bytes:\n   series: ceph_cluster_total_used_bytes\n   opp: counter\n',  # noqa
            'default_dimensions': {'ceph': 'app'}
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes_rate',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_check_derived_metric_type_mismatch(
            self, mock_write_metric, mock_req):
        # Calculation of the derived metric should be skipped when the types
        # don't match, Other metrics should be posted as normal.
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': True,
            'derived_metrics': 'ceph_cluster_usage:\n   x: ceph_cluster_total_used_bytes\n   y: ceph_cluster_total_bytes\n   opp: divide\n   type: gauge\n',  # noqa
            'default_dimensions': {'ceph': 'app'}
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_vanilla_config(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      965648904094.0,
                      dimensions={'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      1300737243057.0,
                      dimensions={'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      2433806018643.0,
                      dimensions={'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_vanilla_config_default_dimensions(
            self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'default_dimensions': {'ceph': 'app'}
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_rate',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_vanilla_config_no_rates(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': False,
            'default_dimensions': {'ceph': 'app'}
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_endpoint_whitelist(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': False,
            'default_dimensions': {'ceph': 'app'},
            'whitelist': ['ceph_cluster.*']
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_endpoint_whitelist_many_items(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'counters_to_rates': False,
            'default_dimensions': {'ceph': 'app'},
            'whitelist': ['ceph_cluster_total_used_bytes',
                          'ceph_cluster_total_bytes',
                          'ceph_osd_op.*']
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_endpoint_returns_nothing(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        # An example of this situation is when scraping a passive Ceph
        # manager which returns no metrics. In that case we still want
        # to scrape the endpoint in case it becomes active.
        mock_req.return_value.text = ''
        # Should not raise an exception.
        self.prometheus.check(instance)
        mock_write_metric.assert_not_called()

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_derived_metric_sum_series(self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'derived_metrics': 'ceph_osd_op_out_bytes_total_sum:\n   series: ceph_osd_op_out_bytes_total\n   key: ceph_daemon\n   opp: sum\n',  # noqa
            'counters_to_rates': False,
            'default_dimensions': {'ceph': 'app'},
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        mock_req.return_value.text = self.example_scrape_output
        self.prometheus.check(instance)
        calls = [
            mock.call(mock.ANY,
                      'ceph_cluster_total_used_bytes',
                      227277146636288.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_cluster_total_bytes',
                      1083703445897216.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      965648904094.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.1',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      1300737243057.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.2',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total',
                      2433806018643.0,
                      dimensions={'ceph': 'app',
                                  'ceph_daemon': 'osd.3',
                                  'hostname': 'squawky'}),
            mock.call(mock.ANY,
                      'ceph_osd_op_out_bytes_total_sum',
                      4700192165794.0,
                      dimensions={'ceph': 'app',
                                  'hostname': 'squawky'}),
        ]
        mock_write_metric.assert_has_calls(calls, any_order=True)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.requests.get')
    @mock.patch('stackhpc_monasca_agent_plugins.checks.'
                'prometheusv2.PrometheusV2._write_metric')
    def test_endpoint_returns_nothing_with_derived(
            self, mock_write_metric, mock_req):
        instance = {
            'metric_endpoint': 'mocked_endpoint',
            'derived_metrics': 'ceph_osd_op_out_bytes_total_sum:\n   series: ceph_osd_op_out_bytes_total\n   key: ceph_daemon\n   opp: sum\n',  # noqa
        }

        mock_req.return_value.headers = {
            'Content-Type': 'text/plain;charset=utf-8'}
        # An example of this situation is when scraping a passive Ceph
        # manager which returns no metrics. In that case we still want
        # to scrape the endpoint in case it becomes active.
        mock_req.return_value.text = ''
        # Should not raise an exception.
        self.prometheus.check(instance)
        mock_write_metric.assert_not_called()

# Test func (get rid of Mock.ANY)
