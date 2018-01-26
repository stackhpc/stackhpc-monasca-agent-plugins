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


class TestSlurm(unittest.TestCase):
    def setUp(self):
        self.slurm = MockSlurmPlugin()

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
            'openhpc-compute-10': {
                'job_id': '689', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-11': {
                'job_id': '689', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-12': {
                'job_id': '690', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-13': {
                'job_id': '690', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-14': {
                'job_id': '690', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-15': {
                'job_id': '690', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-8': {
                'job_id': '689', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-9': {
                'job_id': '689', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-2': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-3': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-0': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-1': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-6': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-7': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-4': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'},
            'openhpc-compute-5': {
                'job_id': '688', 'user_group': 'john',
                'user_id': 'john',
                'job_name': 'test_ompi.sh', 'job_state': 'RUNNING'}
        }
        self.assertEqual(expected, actual)

    def test__get_nodes(self):
        actual = self.slurm._get_nodes()
        expected = {
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

    @mock.patch('monasca_agent.collector.checks.AgentCheck.gauge',
                autospec=True)
    def test_check(self, mock_gauge):
        self.slurm.check('openhpc-login-0')
        metric_name = '{}.{}'.format(slurm._METRIC_NAME_PREFIX,
                                     slurm._METRIC_NAME)
        calls = [
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-18',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-19',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 690.0,
                      device_name='openhpc-compute-14', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 690.0,
                      device_name='openhpc-compute-15', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-16',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-17',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 689.0,
                      device_name='openhpc-compute-10', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 689.0,
                      device_name='openhpc-compute-11', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 690.0,
                      device_name='openhpc-compute-12', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 690.0,
                      device_name='openhpc-compute-13', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 689.0,
                      device_name='openhpc-compute-8', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 689.0,
                      device_name='openhpc-compute-9', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-4', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-5', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-6', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-7', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-0', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-1', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-2', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 688.0,
                      device_name='openhpc-compute-3', dimensions={
                          'user_id': 'john', 'job_state': 'RUNNING',
                          'user_group': 'john', 'instance': 'openhpc-login-0'},
                      value_meta={'job_name': 'test_ompi.sh'}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-21',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-20',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-23',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-22',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-25',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-24',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-27',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={}),
            mock.call(mock.ANY, metric_name, 0.0,
                      device_name='openhpc-compute-26',
                      dimensions={'instance': 'openhpc-login-0'},
                      value_meta={})
        ]
        mock_gauge.assert_has_calls(calls, any_order=True)
