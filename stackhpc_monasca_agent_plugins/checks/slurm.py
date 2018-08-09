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

import monasca_agent.collector.checks as checks
from monasca_agent.common.util import timeout_command

log = logging.getLogger(__name__)

_METRIC_NAME_PREFIX = "slurm"
_METRIC_NAME = "job_status"
_SLURM_LIST_JOBS_CMD = ['/usr/bin/scontrol', '-o', 'show', 'job']
_SLURM_LIST_NODES_CMD = ['/usr/bin/scontrol', '-o', 'show', 'node']

_SLURM_JOB_FIELD_REGEX = ('^JobId=([\d]+)\sJobName=(.*?)\s'
                          'UserId=([\w-]+\([\w-]+\))\sGroupId=([\w-]+\([\w-]+\))\s.*\s'
                          'JobState=([\w]+)\s.*\sRunTime=([:\w-]+)\s'
                          'TimeLimit=([:\w-]+)\s.*\sStartTime=([:\w-]+)\s'
                          'EndTime=([:\w-]+)\s.*\sNodeList=(.*?)\s.*$')
_SLURM_NODE_FIELD_REGEX = '^NodeName=(.*?)\s.*State=(.*?)\s.*$'
_SLURM_NODE_SEQUENCE_REGEX = '^(.*)\[(.*)\]$'

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
        return Slurm._get_raw_data(_SLURM_LIST_NODES_CMD).splitlines()

    @staticmethod
    def _get_raw_job_data():
        return Slurm._get_raw_data(_SLURM_LIST_JOBS_CMD).splitlines()

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
        nodes = { '(null)': None }
        for node in raw_node_data:
            m = pattern.match(node)
            nodes[m.group(1)] = {'node_state': m.group(2)}
        return nodes

    def check(self, instance):
        metric_name = '{0}.{1}'.format(_METRIC_NAME_PREFIX, _METRIC_NAME)
        jobs_by_node = self._get_jobs()
        for node in self._get_nodes():
            jobs = jobs_by_node.get(node, [])
            for job_info in jobs:
                print("job_info: ", job_info)
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
                log.debug('Collected slurm status for node {0}'.format(node))
