# Copyright (c) 2018 StackHPC Ltd.
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
import logging
import re
import traceback

import monasca_agent.collector.checks as checks
from monasca_agent.common.util import timeout_command

log = logging.getLogger(__name__)

_METRIC_NAME_PREFIX = "slurm"
_METRIC_NAME = "job_status"
_SLURM_LIST_JOBS_CMD = ['/usr/bin/scontrol', '-o', 'show', 'job']
_SLURM_LIST_NODES_CMD = ['/usr/bin/scontrol', '-o', 'show', 'node']
_SLURM_CLUSTER_UTILIZATION_CMD = ['/usr/bin/sreport', 'cluster', 'utilization']
_SLURM_LIST_JOB_SIZES_CMD = ['sacct', '--allocations', '--allusers', '--state',
    'RUNNING', '--format', 'TimeLimit']
_SLURM_SDIAG_CMD = ['sdiag']
_SLURM_JOB_STATISTICS = ['sstat', '-j', '<job_id>', '--allsteps',
    '--format=', 'AveCPU,AveDiskRead,AveDiskWrite,AvePages,AveCPUFreq,AveRSS,'
    'AveVMSize,MinCPU,MaxDiskRead,MaxDiskWrite,MaxPages,MaxRSS,MaxVMSize']

_SLURM_JOB_FIELD_REGEX = ('^JobId=([\d]+)\sJobName=(.*?)\s'
                          'UserId=([\w-]+\([\w-]+\))\sGroupId=([\w-]+\([\w-]+\))\s.*\s'
                          'JobState=([\w]+)\s.*\sRunTime=([:\w-]+)\s'
                          'TimeLimit=([:\w-]+)\s.*\sStartTime=([:\w-]+)\s'
                          'EndTime=([:\w-]+)\s.*\sNodeList=(.*?)\s.*$')
_SLURM_NODE_FIELD_REGEX = '^NodeName=(.*?)\s.*State=(.*?)\s.*$'
_SLURM_NODE_SEQUENCE_REGEX = '^(.*)\[(.*)\]$'
_SLURM_CLUSTER_UTILIZATION_REPORT_FIELD_REGEX = ('([\S]+)[\s]+([\d]+)[\s]+([\d]+)[\s]+'
    '([\d]+)[\s]+([\d]+)[\s]+([\d]+)[\s]+([\d]+)')
_SLURM_JOB_STATISTICS_REGEX = '^\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+' \
    '([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)\s+([\S]+)'

_JOB_STATE = {
    "UNKNOWN": 0,  
    "PENDING": 1,       # PD, Awaiting resource allocation
    "RUNNING": 2,       # R, Resources allocated and script executing
    "SUSPENDED": 3,     # S, Job suspended and previously allocated resources released
    "COMPLETING": 4,    # CG, in the process of completing, processes of a job still executing in the background
    "COMPLETED": 5      # CD, job terminated (successfully)
}


class Slurm(checks.AgentCheck):
    def __init__(self, name, init_config, agent_config):
        super(Slurm, self).__init__(name, init_config, agent_config)

    @staticmethod
    def _get_raw_data(cmd, timeout=10):
        # If the command times out, nothing is returned
        stdout, stderr, rc = (
            timeout_command(cmd, timeout) or (None, None, None))
        if rc == 0:
            return stdout
        elif rc is None:
            err_msg = ("Command: {} timed out after {} seconds."
                       .format(cmd, timeout))
        else:
            err_msg = ("Failed to query Slurm. Return code: {0}, error: {1}."
                       .format(rc, stderr))
        raise Exception(err_msg)

    @staticmethod
    def _get_raw_node_data():
        return map(lambda str: str.rstrip(), Slurm._get_raw_data(_SLURM_LIST_NODES_CMD).splitlines())

    @staticmethod
    def _get_raw_job_data():
        return map(lambda str: str.rstrip(), Slurm._get_raw_data(_SLURM_LIST_JOBS_CMD).splitlines())

    @staticmethod
    def _get_raw_cluster_utilisation_report_data():
        return map(lambda str: str.rstrip(), Slurm._get_raw_data(_SLURM_CLUSTER_UTILIZATION_CMD).splitlines())

    @staticmethod
    def _get_job_sizes_data():
        return map(lambda str: str.rstrip(), Slurm._get_raw_data(_SLURM_LIST_JOB_SIZES_CMD).splitlines())

    @staticmethod
    def _get_sdiag_data():
        return Slurm._get_raw_data(_SLURM_SDIAG_CMD)

    @staticmethod
    def _get_job_statistics_data(job_id):
        _SLURM_JOB_STATISTICS[2] = job_id
        return map(lambda str: str.rstrip(), Slurm._get_raw_data(_SLURM_JOB_STATISTICS).splitlines())

    @staticmethod
    def _extract_node_names(field):
        multiple_nodes = re.match(_SLURM_NODE_SEQUENCE_REGEX, field)
        node_names = set()
        if multiple_nodes:
            prefix = multiple_nodes.group(1)
            sequences = multiple_nodes.group(2).split(',')
            # Some example sequences: '1', '1-2', '1,3,5-7', ...
            for s in sequences:
                node_range = s.split('-')
                sequence_start = int(node_range[0])
                sequence_end = int(
                    node_range[1] if len(node_range) == 2 else sequence_start)
                for node in range(sequence_start, sequence_end + 1):
                    node_names.add('{}{}'.format(prefix, node))
        else:
            field = 'null' if field == '(null)' else field
            node_names.add(field)
        return node_names

    @staticmethod
    def _extract_name(field):
        """
        Removes numerical field from user or group

        This will strip off the numerical section from for example john(2000)
        and return 'john'.
        :param field: Username or group and number
        :return: Username or group without number
        """
        return re.sub('[(\d+)]', '', field)

    def _get_jobs(self):
        raw_job_data = self._get_raw_job_data()
        pattern = re.compile(_SLURM_JOB_FIELD_REGEX)
        jobs = {}
        for job in raw_job_data:
            m = pattern.match(job)
            if not m:
                # If there are no jobs there will be no match
                continue
            job = {
                'job_id': m.group(1),
                'job_name': m.group(2),
                'user_id': Slurm._extract_name(m.group(3)),
                'user_group': Slurm._extract_name(m.group(4)),
                'job_state': m.group(5),
                'runtime': m.group(6),
                'time_limit': m.group(7),
                'start_time': m.group(8),
                'end_time': m.group(9)
            }
            # if 'RUNNING' in job['job_state']:
            # Ignore pending jobs for now
            nodes = self._extract_node_names(m.group(10))
            for node in nodes:
                jobs[node] = (jobs[node] if (node in jobs) else []) + [copy.deepcopy(job)]
        return jobs

    def _get_nodes(self):
        raw_node_data = self._get_raw_node_data()
        pattern = re.compile(_SLURM_NODE_FIELD_REGEX)
        nodes = { 'null': None }
        for node in raw_node_data:
            m = pattern.match(node)
            nodes[m.group(1)] = {'node_state': m.group(2)}
        return nodes

    def _get_cluster_utilization_data(self):
        raw_cluster_utilization_report_data = self._get_raw_cluster_utilisation_report_data()[-1]
        pattern = re.compile(_SLURM_CLUSTER_UTILIZATION_REPORT_FIELD_REGEX)
        groups = pattern.match(raw_cluster_utilization_report_data)
        allocated_nodes, reported_nodes = int(groups.group(2)), int(groups.group(7))
        return (allocated_nodes, reported_nodes)

    @staticmethod
    def timelimit_str_to_mins(timelimit_str):
        timelimit_str = timelimit_str.split(".")[0]
        day_time = timelimit_str.split("-")
        day = day_time[0] if len(day_time) > 1 else 0
        try:
            (hrs, mins, secs) = day_time[-1].split(":")
        except:
            hrs = 0
            (mins, secs) = day_time[-1].split(":")
        try:
            secs = int(secs)
        except:
            secs = 0
        return (((int(day) * 24 + int(hrs)) * 60 + int(mins)) * 60 + secs)

    def _get_avg_job_size(self):
        raw_job_sizes_data = self._get_job_sizes_data()[2:]
        job_sizes = map(Slurm.timelimit_str_to_mins, raw_job_sizes_data)
        return sum(job_sizes)/len(job_sizes)

    def _get_queue_length(self):
        raw_sdiag_data = self._get_sdiag_data()
        queue_length = int(re.search("Last queue length:\s([\d]+)", raw_sdiag_data).group(1))
        return queue_length

    def _get_job_statistics(self, job_id):
        job_statistics_data = self._get_job_statistics_data(job_id);
        if len(job_statistics_data) > 2:
            groups = re.match(_SLURM_JOB_STATISTICS_REGEX, job_statistics_data[2]);
            ave_cpu, ave_disk_read, ave_disk_write, ave_pages, ave_cpu_freq, ave_rss, ave_vm_size, \
            min_cpu, max_disk_read, max_disk_write, max_pages, max_rss, max_vm_size = \
                groups.group(1), groups.group(2), groups.group(3), groups.group(4), groups.group(5), \
                groups.group(6), groups.group(7), groups.group(8), groups.group(9), groups.group(10), \
                groups.group(11), groups.group(12), groups.group(13)
            return (ave_cpu, ave_disk_read, ave_disk_write, ave_pages, ave_cpu_freq, ave_rss, ave_vm_size, \
            min_cpu, max_disk_read, max_disk_write, max_pages, max_rss, max_vm_size)
        else:
            raise Exception("failed to collect statistics from sstat")

    def check(self, instance):
        metric_name = '{0}.{1}'.format(_METRIC_NAME_PREFIX, _METRIC_NAME)
        jobs_by_node = self._get_jobs()
        for node in self._get_nodes():
            jobs = jobs_by_node.get(node, [])
            for job_info in jobs:
                job_info.update({ 'hostname': node })
                # TODO - If node is down set to -1?
                metric_value = _JOB_STATE.get(job_info.pop('job_state', 'UNKNOWN'), _JOB_STATE.get('UNKNOWN'))
                # Save the job name as metadata. For one, it's likely to have
                # characters which aren't valid in a dimension.
                value_meta = { 
                    'job_name': job_info.pop('job_name', 'job_' + job_info.get('job_id')),
                    'runtime': job_info.pop('runtime', "Unknown"),
                    'time_limit': job_info.pop('time_limit', "Unknown"),
                    'start_time': job_info.pop('start_time', "Unknown"),
                    'end_time': job_info.pop('end_time', "Unknown")
                }
                dimensions = self._set_dimensions(job_info, instance)
                
                self.gauge(metric_name,
                        metric_value,
                        device_name=node,
                        dimensions=dimensions,
                        value_meta=value_meta)
                log.debug('Collected slurm status for job {0} node {1}'.format(job_info.get('job_id'), node))

                if metric_value == 2:
                    try:
                        ave_cpu, ave_disk_read, ave_disk_write, ave_pages, ave_cpu_freq, ave_rss, ave_vm_size, \
                        min_cpu, max_disk_read, max_disk_write, max_pages, max_rss, max_vm_size = \
                            self._get_job_statistics(job_info.get('job_id'))
                        self.gauge("slurm.ave_cpu",
                            Slurm.timelimit_str_to_mins(ave_cpu),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.ave_disk_read_mb",
                            float(re.match("^([.\d]+)M$", ave_disk_read).group(1)),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.ave_disk_write_mb",
                            float(re.match("^([.\d]+)M$", ave_disk_write).group(1)),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.ave_pages",
                            int(ave_pages),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.ave_cpu_freq_ghz",
                            float(re.match("^([.\d]+)G$", ave_cpu_freq).group(1)),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.ave_rss_mb",
                            float(re.match("^([.\d]+)K$", ave_rss).group(1))/1000,
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.ave_vm_size_mb",
                            float(re.match("^([.\d]+)K$", ave_vm_size).group(1))/1000,
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.min_cpu",
                            Slurm.timelimit_str_to_mins(min_cpu),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.max_disk_read_mb",
                            float(re.match("^([.\d]+)M$", max_disk_read).group(1)),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.max_disk_write_mb",
                            float(re.match("^([.\d]+)M$", max_disk_write).group(1)),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.max_pages",
                            int(max_pages),
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.max_rss_mb",
                            float(re.match("^([.\d]+)K$", max_rss).group(1))/1000,
                            device_name=node,
                            dimensions=dimensions)
                        self.gauge("slurm.max_vm_size_mb",
                            float(re.match("^([.\d]+)K$", max_vm_size).group(1))/1000,
                            device_name=node,
                            dimensions=dimensions)
                        log.debug('Collected slurm statistics for job {0} node {1}'.format(job_info.get('job_id'), node))
                    except Exception as e:
                        log.debug("slurm exception: {}".format(e.message))
                        traceback.print_exc()

        try:
            allocated_nodes, reported_nodes = self._get_cluster_utilization_data()
            self.gauge("cluster.slurm_utilization",
                       allocated_nodes / reported_nodes)
            avg_job_size = self._get_avg_job_size()
            self.gauge("slurm.avg_job_size",
                    avg_job_size)
            queue_length = self._get_queue_length()
            self.gauge("slurm.queue_length",
                       queue_length)
        except Exception as exp:
            pass
