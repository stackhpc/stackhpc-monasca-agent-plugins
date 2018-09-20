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

import os
import unittest

import mock

import stackhpc_monasca_agent_plugins.checks.slurm as slurm

# Example output from $ scontrol -o show node
_EXAMPLE_SLURM_NODE_LIST_FILENAME = 'example_slurm_node_list'

# Example output from $ scontrol -o show job
_EXAMPLE_SLURM_JOB_LIST_FILENAME = 'example_slurm_job_list'

# Example output from $ sreport cluster utilization
_EXAMPLE_SLURM_CLUSTER_UTILIZATION_REPORT = \
    'example_cluster_utilization_report'

# Example output from $ sacct --allocations --allusers --state=RUNNING
# --format=TimeLimit
_EXAMPLE_SLURM_JOB_SIZE_LIST = 'example_job_size_list'

# Example output from $ sacct --allocations --allusers --state=RUNNING
# --format=TimeLimit
_EXAMPLE_SDIAG_FILENAME = 'example_sdiag'

# Example successful output from sstat
_EXAMPLE_JOB_STATISTICS_FILENAME = 'example_job_statistics'

# Example failed output from sstat
_EXAMPLE_JOB_STATISTICS_EMPTY_FILENAME = 'example_job_statistics_empty'


class MockSlurmPlugin(slurm.Slurm):
    def __init__(self):
        # Don't call the base class constructor
        pass

    @staticmethod
    def _set_dimensions(dimensions, instance=None):
        if instance:
            dimensions['instance'] = instance
        return dimensions

    @staticmethod
    def _get_raw_data(filename):
        filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            filename)
        with open(filepath, 'r') as f:
            contents = f.readlines()
        return contents

    @staticmethod
    def _get_raw_job_data():
        return MockSlurmPlugin._get_raw_data(_EXAMPLE_SLURM_JOB_LIST_FILENAME)

    @staticmethod
    def _get_raw_node_data():
        return MockSlurmPlugin._get_raw_data(_EXAMPLE_SLURM_NODE_LIST_FILENAME)

    @staticmethod
    def _get_raw_cluster_utilisation_report_data():
        return MockSlurmPlugin._get_raw_data(
            _EXAMPLE_SLURM_CLUSTER_UTILIZATION_REPORT)

    @staticmethod
    def _get_job_sizes_data():
        return MockSlurmPlugin._get_raw_data(
            _EXAMPLE_SLURM_JOB_SIZE_LIST)

    @staticmethod
    def _get_sdiag_data():
        return "\n".join(MockSlurmPlugin._get_raw_data(
            _EXAMPLE_SDIAG_FILENAME))

    @staticmethod
    def _get_job_statistics_data_success(job_id):
        return MockSlurmPlugin._get_raw_data(
            _EXAMPLE_JOB_STATISTICS_FILENAME)

    @staticmethod
    def _get_job_statistics_data_failed(job_id):
        return MockSlurmPlugin._get_raw_data(
            _EXAMPLE_JOB_STATISTICS_EMPTY_FILENAME)


class TestSlurm(unittest.TestCase):
    def setUp(self):
        self.slurm = MockSlurmPlugin()

    @mock.patch('stackhpc_monasca_agent_plugins.checks.slurm.timeout_command')
    def test__get_raw_data_failed(self, mock_timeout_command):
        err_msg = 'something terrible'
        mock_timeout_command.return_value = ('', err_msg, 1)
        self.assertRaisesRegexp(
            Exception,
            'Failed to query Slurm. Return code: 1, error: {}'.format(err_msg),
            slurm.Slurm._get_raw_data, 'doomed cmd', timeout=5)
        mock_timeout_command.assert_called_with('doomed cmd', 5)

    @mock.patch('stackhpc_monasca_agent_plugins.checks.slurm.timeout_command')
    def test__get_raw_data_timed_out(self, mock_timeout_command):
        cmd = 'slow cmd'
        mock_timeout_command.return_value = None
        self.assertRaisesRegexp(
            Exception,
            'Command: {} timed out after 5 seconds.'.format(cmd),
            slurm.Slurm._get_raw_data, cmd, timeout=5)
        mock_timeout_command.assert_called_with(cmd, 5)

    @mock.patch('stackhpc_monasca_agent_plugins.tests.unit.checks.test_slurm.'
                'MockSlurmPlugin._get_raw_job_data')
    def test__get_jobs_none(self, mock_job_data):
        mock_job_data.return_value = 'No jobs in the system'
        actual = self.slurm._get_jobs()
        expected = {}
        self.assertEqual(expected, actual)

    def test__extract_node_names_series(self):
        field = "openhpc-compute-[0-2]"
        expected = {
            'openhpc-compute-0',
            'openhpc-compute-1',
            'openhpc-compute-2',
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_node_names_single_node(self):
        field = "openhpc-compute-17"
        expected = {
            'openhpc-compute-17'
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_node_names_discontinuous(self):
        field = "openhpc-compute-[1,15]"
        expected = {
            'openhpc-compute-1',
            'openhpc-compute-15',
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_node_names_series_discontinuous(self):
        field = "openhpc-compute-[1-3,5]"
        expected = {
            'openhpc-compute-1',
            'openhpc-compute-2',
            'openhpc-compute-3',
            'openhpc-compute-5',
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_node_names_series_multiple_discontinuous(self):
        field = "openhpc-compute-[1-3,5,7-9,11]"
        expected = {
            'openhpc-compute-1',
            'openhpc-compute-2',
            'openhpc-compute-3',
            'openhpc-compute-5',
            'openhpc-compute-7',
            'openhpc-compute-8',
            'openhpc-compute-9',
            'openhpc-compute-11'
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_name(self):
        field = "john(2000)"
        actual = self.slurm._extract_name(field)
        self.assertEqual('john', actual)

    def test__extract_node_names_series_multiple_digits(self):
        field = "openhpc-compute-[99-101]"
        expected = {
            'openhpc-compute-99',
            'openhpc-compute-100',
            'openhpc-compute-101',
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_node_names_single(self):
        field = "openhpc-compute-3"
        expected = {
            'openhpc-compute-3'
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__extract_node_names_single_multiple_digits(self):
        field = "openhpc-compute-1343"
        expected = {
            'openhpc-compute-1343'
        }
        actual = self.slurm._extract_node_names(field)
        self.assertEqual(expected, actual)

    def test__get_jobs(self):
        actual = self.slurm._get_jobs()
        expected = {
            'null': [{
                'job_id': '691', 'job_name': 'test_ompi.sh',
                'job_state': 'PENDING', 'user_group': 'john',
                'user_id': 'john', 'runtime': '00:00:00',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-26T12:05:46',
                'end_time': '2018-01-27T12:05:46'}, {
                'job_id': '692', 'job_name': 'test_ompi.sh',
                'job_state': 'PENDING', 'user_group': 'john',
                'user_id': 'john', 'runtime': '00:00:00',
                'time_limit': '1-00:00:00', 'start_time': 'Unknown',
                'end_time': 'Unknown'}],
            'openhpc-compute-0': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-1': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-2': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-3': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-4': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-5': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-6': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-7': [{
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john', 'job_name': 'test_ompi.sh',
                'job_state': 'RUNNING', 'runtime': '01:53:03',
                'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T11:53:42',
                'end_time': '2018-01-26T11:53:42'}],
            'openhpc-compute-8': [{
                'job_id': '689', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:43:49', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:02:56',
                'end_time': '2018-01-26T12:02:56'}],
            'openhpc-compute-9': [{
                'job_id': '689', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:43:49', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:02:56',
                'end_time': '2018-01-26T12:02:56'}],
            'openhpc-compute-10': [{
                'job_id': '689', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:43:49', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:02:56',
                'end_time': '2018-01-26T12:02:56'}],
            'openhpc-compute-11': [{
                'job_id': '689', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:43:49', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:02:56',
                'end_time': '2018-01-26T12:02:56'}],
            'openhpc-compute-12': [{
                'job_id': '690', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:40:59', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:05:46',
                'end_time': '2018-01-26T12:05:46'}],
            'openhpc-compute-13': [{
                'job_id': '690', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:40:59', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:05:46',
                'end_time': '2018-01-26T12:05:46'}],
            'openhpc-compute-14': [{
                'job_id': '690', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:40:59', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:05:46',
                'end_time': '2018-01-26T12:05:46'}],
            'openhpc-compute-15': [{
                'job_id': '690', 'user_group': 'john', 'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING',
                'runtime': '01:40:59', 'time_limit': '1-00:00:00',
                'start_time': '2018-01-25T12:05:46',
                'end_time': '2018-01-26T12:05:46'}]
        }
        self.maxDiff = None
        self.assertEqual(expected, actual)

    def test__get_nodes(self):
        actual = self.slurm._get_nodes()
        expected = {
            'null': None,
            'openhpc-compute-17': {'node_state': 'DOWN*'},
            'openhpc-compute-16': {'node_state': 'DOWN*'},
            'openhpc-compute-15': {'node_state': 'IDLE'},
            'openhpc-compute-14': {'node_state': 'IDLE'},
            'openhpc-compute-13': {'node_state': 'IDLE'},
            'openhpc-compute-12': {'node_state': 'IDLE'},
            'openhpc-compute-11': {'node_state': 'IDLE'},
            'openhpc-compute-10': {'node_state': 'IDLE'},
            'openhpc-compute-19': {'node_state': 'DOWN*'},
            'openhpc-compute-18': {'node_state': 'DOWN*'},
            'openhpc-compute-22': {'node_state': 'DOWN*'},
            'openhpc-compute-23': {'node_state': 'DOWN*'},
            'openhpc-compute-20': {'node_state': 'DOWN*'},
            'openhpc-compute-21': {'node_state': 'DOWN*'},
            'openhpc-compute-26': {'node_state': 'DOWN*'},
            'openhpc-compute-27': {'node_state': 'DOWN*'},
            'openhpc-compute-24': {'node_state': 'DOWN*'},
            'openhpc-compute-25': {'node_state': 'DOWN*'},
            'openhpc-compute-1': {'node_state': 'IDLE'},
            'openhpc-compute-0': {'node_state': 'IDLE'},
            'openhpc-compute-3': {'node_state': 'IDLE'},
            'openhpc-compute-2': {'node_state': 'IDLE'},
            'openhpc-compute-5': {'node_state': 'IDLE'},
            'openhpc-compute-4': {'node_state': 'IDLE'},
            'openhpc-compute-7': {'node_state': 'IDLE'},
            'openhpc-compute-6': {'node_state': 'IDLE'},
            'openhpc-compute-9': {'node_state': 'IDLE'},
            'openhpc-compute-8': {'node_state': 'IDLE'}
        }
        self.assertEqual(expected, actual)

    def test__get_cluster_utilization_data(self):
        allocated_nodes, reported_nodes = self. \
            slurm._get_cluster_utilization_data()
        self.assertEqual(allocated_nodes, 20117847)
        self.assertEqual(reported_nodes, 23195520)

    def test__get_avg_job_size(self):
        avg_job_size = self.slurm._get_avg_job_size()
        self.assertEqual(avg_job_size, 415500)

    def test__get_queue_length(self):
        queue_length = self.slurm._get_queue_length()
        self.assertEqual(queue_length, 30)

    def test__get_job_statistics(self):
        self.slurm._get_job_statistics_data = self. \
            slurm._get_job_statistics_data_failed
        self.assertRaises(Exception, self.slurm._get_job_statistics, 1000)

        self.slurm._get_job_statistics_data = self. \
            slurm._get_job_statistics_data_success
        ave_cpu, ave_disk_read, ave_disk_write, ave_pages, ave_cpu_freq, \
            ave_rss, ave_vm_size, min_cpu, max_disk_read, \
            max_disk_write, max_pages, max_rss, max_vm_size = \
            self.slurm._get_job_statistics(1000)
        self.assertEqual(ave_cpu, "00:05.000")
        self.assertEqual(ave_disk_read, "1.39M")
        self.assertEqual(ave_disk_write, "0.00M")
        self.assertEqual(ave_pages, "0")
        self.assertEqual(ave_cpu_freq, "2.40K")
        self.assertEqual(ave_rss, "125576K")
        self.assertEqual(ave_vm_size, "21722468K")
        self.assertEqual(min_cpu, "00:04.000")
        self.assertEqual(max_disk_read, "1.40M")
        self.assertEqual(max_disk_write, "0.00M")
        self.assertEqual(max_pages, "0")
        self.assertEqual(max_rss, "126308K")
        self.assertEqual(max_vm_size, "21724660K")

    @mock.patch('monasca_agent.collector.checks.AgentCheck.gauge',
                autospec=True)
    def test_check(self, mock_gauge):
        self.slurm._get_job_statistics_data = self. \
            slurm._get_job_statistics_data_success
        self.slurm.check('openhpc-login-0')
        status_metric_name = '{}.{}'.format(
            slurm._METRIC_NAME_PREFIX, "job_status")

        calls = [
            mock.call(mock.ANY, status_metric_name, 1,
                      device_name='null',
                      dimensions={
                          'user_id': 'john', 'job_id': "691",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'null'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '00:00:00',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-26T12:05:46',
                          'end_time': '2018-01-27T12:05:46'
                          }),
            mock.call(mock.ANY, status_metric_name, 1,
                      device_name='null',
                      dimensions={
                          'user_id': 'john', 'job_id': "692",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'null'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '00:00:00',
                          'time_limit': '1-00:00:00',
                          'start_time': 'Unknown',
                          'end_time': 'Unknown'
                          }),
            mock.call(mock.ANY, status_metric_name, 2,
                      device_name='openhpc-compute-0',
                      dimensions={
                          'user_id': 'john', 'job_id': "688",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-0'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '01:53:03',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-25T11:53:42',
                          'end_time': '2018-01-26T11:53:42'
                          }),
            mock.call(mock.ANY, status_metric_name, 2,
                      device_name='openhpc-compute-1', dimensions={
                          'user_id': 'john', 'job_id': "688",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-1'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '01:53:03',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-25T11:53:42',
                          'end_time': '2018-01-26T11:53:42'
                          }),
            mock.call(mock.ANY, status_metric_name, 2,
                      device_name='openhpc-compute-8',
                      dimensions={
                          'user_id': 'john', 'job_id': "689",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-8'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '01:43:49',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-25T12:02:56',
                          'end_time': '2018-01-26T12:02:56'
                          }),
            mock.call(mock.ANY, status_metric_name, 2,
                      device_name='openhpc-compute-9',
                      dimensions={
                          'user_id': 'john', 'job_id': "689",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-9'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '01:43:49',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-25T12:02:56',
                          'end_time': '2018-01-26T12:02:56'
                          }),
            mock.call(mock.ANY, status_metric_name, 2,
                      device_name='openhpc-compute-12',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-12'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '01:40:59',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-25T12:05:46',
                          'end_time': '2018-01-26T12:05:46'
                          }),
            mock.call(mock.ANY, status_metric_name, 2,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'},
                      value_meta={
                          'job_name': 'test_ompi.sh',
                          'runtime': '01:40:59',
                          'time_limit': '1-00:00:00',
                          'start_time': '2018-01-25T12:05:46',
                          'end_time': '2018-01-26T12:05:46'
                          }),
            mock.call(mock.ANY, "cluster.slurm_utilization",
                      20117847 / 23195520),
            mock.call(mock.ANY, "slurm.avg_job_size",
                      415500),
            mock.call(mock.ANY, "slurm.queue_length",
                      30),
            mock.call(mock.ANY, "slurm.ave_cpu_mins", 5,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.ave_disk_read_mb", 1.39,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.ave_disk_write_mb", 0.00,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.ave_pages_kb", 0.0,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.ave_cpu_freq_khz", 2.40,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.ave_rss_kb", 125576,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.ave_vm_size_kb", 21722468,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.min_cpu_mins", 4,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.max_disk_read_mb", 1.40,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.max_disk_write_mb", 0.00,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.max_pages_kb", 0.0,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.max_rss_kb", 126308,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'}),
            mock.call(mock.ANY, "slurm.max_vm_size_kb", 21724660,
                      device_name='openhpc-compute-13',
                      dimensions={
                          'user_id': 'john', 'job_id': "690",
                          'user_group': 'john', 'instance': 'openhpc-login-0',
                          'hostname': 'openhpc-compute-13'})
        ]

        mock_gauge.assert_has_calls(calls, any_order=True)
