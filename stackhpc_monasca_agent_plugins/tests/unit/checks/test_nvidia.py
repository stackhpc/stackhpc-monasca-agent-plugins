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

import unittest

import mock
from py3nvml import py3nvml as pynvml
import stackhpc_monasca_agent_plugins.checks.nvidia as nvidia


class MockNvidiaPlugin(nvidia.Nvidia):
    def __init__(self):
        # Don't call the base class constructor
        pass

    @staticmethod
    def _set_dimensions(dimensions, instance=None):
        return {'hostname': 'dummy_hostname'}


class TestNvidiaNetwork(unittest.TestCase):
    def setUp(self):
        self.nvidia = MockNvidiaPlugin()

    @mock.patch('py3nvml.py3nvml.nvmlSystemGetDriverVersion',
                autospec=True)
    def test_dummy_property(self, mock_nvml_call):
        mock_nvml_call.return_value = 'v1.2.3'
        actual = self.nvidia._get_driver_version()
        expected = {'driver_version': 'v1.2.3'}
        self.assertDictEqual(actual, expected)

    @mock.patch('py3nvml.py3nvml.nvmlSystemGetDriverVersion',
                autospec=True)
    def test_unsupported_property(self, mock_nvml_call):
        excp = pynvml.NVMLError(pynvml.NVML_ERROR_NOT_SUPPORTED)
        mock_nvml_call.side_effect = excp
        actual = self.nvidia._get_driver_version()
        expected = {}
        self.assertDictEqual(actual, expected)
