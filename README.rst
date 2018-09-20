==============================
StackHPC Monasca-Agent plugins
==============================

.. image:: https://travis-ci.org/stackhpc/stackhpc-monasca-agent-plugins.svg?branch=master
   :target: https://travis-ci.org/stackhpc/stackhpc-monasca-agent-plugins

A collection of Monasca-Agent plugins to gather metrics.

Includes:

* Infiniband metrics
* Slurm (proof-of-concept)

-----
Slurm
-----
The plugin requires the agent to be running with root permissions to have unrestricted access to slurm data through slurm commands.
Sample config:

.. code::

  init_config: null
  instances:
  - built_by: SlurmDetect
    name: slurm_stats

When run by the monasca-agent on a host with access to the slurm commands, the plugin will query and collect metrics dependant on your slurm configuration and installed plugins

Job State
=========

=============== ======================================================
| Metric Name   slurm.job_status
| Dimensions    user_id, job_id, user_group, hostname
| Value Meta    job_name, runtime, time_limit, start_time, end_time
| Semantics     Current state of job
| Requirements  Slurm
=============== ======================================================

===== ==========
Value  State
----- ----------
0     UNKNOWN
1     PENDING
2     RUNNING
3     SUSPENDED
4     COMPLETING
5     COMPLETED
===== ==========

Cluster Utilizaton
==================

=============== ======================================================
| Metric Name   slurm.slurm_utilization
| Dimensions    None
| Value Meta    None
| Semantics     Fraction (ie 0 < value < 1) of nodes on cluster where jobs are allocated
| Requirements  Slurm, slurmdbd plugin (Slurm Database)
=============== ======================================================

Average Job Size
================

=============== ======================================================
| Metric Name   slurm.avg_job_size
| Dimensions    None
| Value Meta    None
| Semantics     Average job size in minutes
| Requirements  Slurm
=============== ======================================================

Slurm Queue Depth
=================

=============== ======================================================
| Metric Name   slurm.queue_depth
| Dimensions    None
| Value Meta    None
| Semantics     Slurm queue depth (ie. number of jobs pending)
| Requirements  Slurm
=============== ======================================================

Job Specific Metrics
====================
Requirements - Slurm, jobacct_gather slurm plugin

=======================  ===================================== =========== ============================================
Metric Name              Dimensions                            Value Meta  Semantics
-----------------------  ------------------------------------- ----------- --------------------------------------------
slurm.ave_cpu_freq_khz   user_id, job_id, user_group, hostname None        Average Frequency in Kilo Hz
slurm.ave_cpu_mins       user_id, job_id, user_group, hostname None        CPU time (user + system) for job in minutes
slurm.ave_disk_read_mb   user_id, job_id, user_group, hostname None        Average disk read in Mega Bytes
slurm.ave_disk_write_mb  user_id, job_id, user_group, hostname None        Average disk write in Mega Bytes
slurm.ave_pages_kb       user_id, job_id, user_group, hostname None        Average Pages in Kilo Bytes
slurm.ave_rss_kb         user_id, job_id, user_group, hostname None        Average Resident Set Size (RSS) in Kilo Bytes
slurm.ave_vm_size_kb     user_id, job_id, user_group, hostname None        Average VM size in Kilo Bytes
slurm.min_cpu_mins       user_id, job_id, user_group, hostname None        Min CPU time in minutes
slurm.max_disk_read_mb   user_id, job_id, user_group, hostname None        Max disk read in Mega Bytes
slurm.max_disk_write_mb  user_id, job_id, user_group, hostname None        Max disk write in Mega Bytes
slurm.max_pages_kb       user_id, job_id, user_group, hostname None        Max Pages in Kilo Bytes
slurm.max_rss_kb         user_id, job_id, user_group, hostname None        Max Resident Set Size (RSS) in Kilo Bytes
slurm.max_vm_size_kb     user_id, job_id, user_group, hostname None        Max VM size in Kilo Bytes
=======================  ===================================== =========== ============================================
