==============================
StackHPC Monasca-Agent plugins
==============================

.. image:: https://travis-ci.org/stackhpc/stackhpc-monasca-agent-plugins.svg?branch=master
   :target: https://travis-ci.org/stackhpc/stackhpc-monasca-agent-plugins

A collection of Monasca-Agent plugins to gather metrics. This repo functions as an
incubator, with the ultimate aim to merge any effective plugins into the Monasca-Agent.

Includes:

* Infiniband metrics
* Slurm (proof-of-concept)
* nVidia GPUs
* Prometheus (proof-of-concept)

-----------------
Prometheus plugin
-----------------

This is an experimental plugin which extends the capability of the existing
Prometheus plugin to make it more useful. The following configuration
options are supported:

metric_endpoint
===============

The Prometheus endpoint to scrape.

Example:

.. code-block:: yaml

    metric_endpoint: "http://ceph-host:9283/metrics"

remove_hostname
===============

Strip the hostname from each metric. This is useful when scraping an endpoint
which exposes metrics not specific to a host. For example, RabbitMQ queue
lengths, of Ceph cluster health.

Example:

.. code-block:: yaml

    remove_hostname: true

default_dimensions
==================

A dict of dimensions to include with all metrics scraped from the specified
endpoint.

Example:

.. code-block:: yaml

    default_dimensions:
      cluster_tag: production

counters_to_rates
=================

Automatically convert counters to rates. This works by buffering counters
locally and then computing the derivative with respect to time when the
buffer is flushed to the Monasca API. When enabled, this setting uses the
Prometheus metric type to automatically generate new rate metrics from
counters. The counter metrics are still posted to the API unless they
are not included in the ``whitelist``. The rate metrics are named after
the counters by appending ``_rate`` to the end of the metric name. Note that
the Prometheus convention is to append ``_total`` to all counters, so a
counter named ``ceph_osd_op_w`` will become ``ceph_osd_op_w_total_rate``
when converted to a rate.

Example:

.. code-block:: yaml

    counters_to_rates: True

Defaults to ``True``.

whitelist
=========

A whitelist of regexes used to determine which metrics are posted to the
Monasca API. Many Prometheus endpoints generate vast quantities of data,
so this can be a useful way to cut back on the number of metrics posted to
the Monasca API to improve performance.

Example:

.. code-block:: yaml

    whitelist:
      - ceph_cluster_total_used_bytes
      - ceph_cluster_total_bytes
      - ceph_osd_op.*

derived_metrics
===============

A dict of metrics to derive from existing metrics. Supported operations
are ``divide``, ``sum`` and ``counter``.

divide
^^^^^^

The ``divide`` operation divides two metric series by each other. It enforces
that the dimensions of the metrics match, to reduce the chance of an
unphysical result. For example, in a ceph cluster with two OSDs, the
following metrics may exist:

.. code-block::

    ['ceph_osd_total_bytes', 'dimensions': {'osd': 1}, 'value': '1234',
     'ceph_osd_total_bytes', 'dimensions': {'osd': 2}, 'value': '4567']

    ['ceph_osd_total_used_bytes', 'dimensions': {'osd': 1}, 'value': '891',
     'ceph_osd_total_used_bytes', 'dimensions': {'osd': 2}, 'value': '111']

To calculate the fractional amount of space used on each OSD you must
divide ``ceph_osd_total_used_bytes`` by ``ceph_osd_total_bytes`` for ``osd: 1``
and again for ``osd: 2``. The plugin does this by hashing the dimensions for
each metric and using the hash to find the equivalent metric. If the two
metric series do not have common sets of dimensions the operation will
currently fail.

.. code-block::

    derived_metrics:
      ceph_cluster_usage:
        x: ceph_cluster_total_used_bytes
        y: ceph_cluster_total_bytes
        opp: divide

sum
^^^

The ``sum`` operation sums all metrics in a series as a function of a specified
dimension. For example, by specifying the ``osd`` dimension the total space used
on all OSDs could be computed from the following metrics:

.. code-block::

    ['ceph_osd_total_used_bytes', 'dimensions': {'osd': 1}, 'value': '891',
     'ceph_osd_total_used_bytes', 'dimensions': {'osd': 2}, 'value': '111']

If additional dimensions are present, these must remain the same for all
metrics in the calculation. For example, it is not currently possible to
create a ``sum`` on this hypothetical metric series:

.. code-block::

    ['ceph_osd_total_used_bytes', 'dimensions': {'osd': 1, 'cluster: 'A'}, 'value': '891',
     'ceph_osd_total_used_bytes', 'dimensions': {'osd': 1, 'cluster: 'B'}, 'value': '111']

Example:

.. code-block::

    derived_metrics:
      ceph_osd_in_sum:
        series: ceph_osd_in
        key: ceph_daemon
        opp: sum

counter
^^^^^^^

In many cases you will want to use ``counters_to_rates`` to automatically
create counters from rates. However, sometimes Prometheus metrics may not
be marked as counters correctly, or you may want to calculate the rate
of change of a gauge. For example, the rate of change of remaining capacity
would be a useful derivative of a gauge on a Ceph cluster. In this case
you can use the ``counter`` operation to generate a rate from an
arbitrary metric. The new metric assumes the name specified by the
configuration key. For example in this case, a series of metrics called
``ceph_pool_wr_bytes_total_rate`` would be created from the metric series
``ceph_pool_wr_bytes``.


Example:

.. code-block::

    derived_metrics:
      ceph_pool_wr_bytes_total:
        series: ceph_pool_wr_bytes
        opp: counter

Note that this requires ``counters_to_rates`` to be enabled, which is the
default.

Full example configuration
==========================

.. code-block::

    init_config:
      timeout: 10
    instances:
      - metric_endpoint: 'http://ceph-node:9283/metrics'
	remove_hostname: true
	default_dimensions:
	  cluster_tag: production
        counters_to_rates: True
        whitelist:
          - ceph_cluster_total_used_bytes
          - ceph_cluster_total_bytes
          - ceph_osd_op.*
	derived_metrics: |
	  ceph_cluster_usage:
	    x: ceph_cluster_total_used_bytes
	    y: ceph_cluster_total_bytes
	    opp: divide
	  ceph_osd_in_sum:
	    series: ceph_osd_in
	    key: ceph_daemon
	    opp: sum
	  ceph_pool_wr_bytes_total:
	    series: ceph_pool_wr_bytes
	    opp: counter
	  ceph_pool_rd_bytes_total:
	    series: ceph_pool_rd_bytes
	    opp: counter

Note that more than one endpoint can be monitored by adding additional
entries on the ``instances`` list.
