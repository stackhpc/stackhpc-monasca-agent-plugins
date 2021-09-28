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

import logging

import monasca_agent.collector.checks as checks
import subprocess


log = logging.getLogger(__name__)

_METRIC_NAME_PREFIX = "nvidia"
_VGPU_METRIC_NAME_PREFIX = "vgpu"


def _convert_percent_str2float(percent_str):
    # Remove '%' at the end and convert to float
    ts = percent_str.replace('%', '').strip()
    if ts.isnumeric():
        return float(ts)
    return float('NaN')


class Nvidiasmi():

    vgpu_info = []

    def __init__(self):
        pass

    @classmethod
    def get_vgpu_info(cls):
        # It queries vgpu infor using nvidia-smi vgpu command and convert the output
        # into a python dict array.
        # Expected result is;
        # # GPU 00000000:3B:00.0
        # # Active vGPUs                      : 3
        # # vGPU ID                           : 3251635087
        # #     VM UUID                       : 5c0038dc-4129-4dc3-8b64-20d309565abb
        # #     VM Name                       : instance-00002903
        # #     vGPU Name                     : GRID V100D-8Q
        # #     vGPU Type                     : 183
        # #     vGPU UUID                     : d2668621-addf-11eb-94cf-ca3b2a15ab98
        # #     Utilization
        # #         Gpu                       : 0 %
        # #         Memory                    : 0 %
        # #         Encoder                   : 0 %
        # #         Decoder                   : 0 %

        active_vgpu_key = "Active vGPUs"
        vgpu_id_key = "vGPU ID"

        cls.vgpu_info = []

        sp = subprocess.Popen(['nvidia-smi', 'vgpu', '-q'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_str = sp.communicate()
        out_list = out_str[0].decode("utf-8").split('\n')

        cnt = -1
        for item in out_list:
            try:
                key, val = item.split(':')
                key, val = key.strip(), val.strip()
                if key == active_vgpu_key:
                    continue
                if key == vgpu_id_key:
                    cls.vgpu_info.append({})
                    cnt += 1
                cls.vgpu_info[cnt][key] = val
            except:
                pass

    @classmethod
    def get_vgpu_count(cls):
        return len(cls.vgpu_info)

    @classmethod
    def get_vgpu_utilisation_stats(cls, index):
        # Returns the utilization infor of the vgpu[index]
        # index is not a vgpu property, it is just a number indicating vgpu order
        # in the vgpu query result array, vgpu_info, which is fetched in get_vgpu_info
        # function.
        return {
            'utilisation_gpu_percent': _convert_percent_str2float(cls.vgpu_info[index].get("Gpu")),
            'utilisation_memory_percent': _convert_percent_str2float(cls.vgpu_info[index].get("Memory")),
            'utilisation_encoder_percent': _convert_percent_str2float(cls.vgpu_info[index].get("Encoder")),
            'utilisation_decoder_percent': _convert_percent_str2float(cls.vgpu_info[index].get("Decoder"))
        }

    @classmethod
    def get_vgpu_id(cls, index):
        return {'id': cls.vgpu_info[index].get("vGPU ID")}

    @classmethod
    def get_vgpu_uuid(cls, index):
        return {'uuid': cls.vgpu_info[index].get("vGPU UUID")}

    @classmethod
    def get_vgpu_name(cls, index):
        return {'name': cls.vgpu_info[index].get("vGPU Name")}

    @classmethod
    def get_vgpu_vm_uuid(cls, index):
        return {'uuid': cls.vgpu_info[index].get("VM UUID")}

    @classmethod
    def get_vgpu_vm_name(cls, index):
        return {'vm_name': cls.vgpu_info[index].get("VM Name")}


class NvidiaVgpu(checks.AgentCheck):
    def __init__(self, name, init_config, agent_config):
        super(Nvidia, self).__init__(name, init_config, agent_config)

    @staticmethod
    def _get_vgpu_info():
        cnsmi = Nvidiasmi()
        cnsmi.get_vgpu_info()
        vgpu_count = cnsmi.get_vgpu_count()
        all_info = []

        for i in range(0, vgpu_count):
            dimensions = {}
            dimensions.update(cnsmi.get_vgpu_id(i))
            dimensions.update(cnsmi.get_vgpu_uuid(i))
            dimensions.update(cnsmi.get_vgpu_vm_uuid(i))
            dimensions.update(cnsmi.get_vgpu_vm_name(i))

            measurements = {}
            measurements.update(cnsmi.get_vgpu_utilisation_stats(i))

            vgpu_name = "{}_{}".format(
                cnsmi.get_vgpu_name(i).get('name'),
                cnsmi.get_vgpu_id(i).get('id'))
            all_info.append({
                'name': vgpu_name,
                'dimensions': dimensions,
                'measurements': measurements
            })
        return all_info

    def check(self, instance):
        for vgpu_metrics in NvidiaVgpu._get_vgpu_info():
            for measurement, value in vgpu_metrics['measurements'].items():
                metric_name = '{0}.{1}.{2}'.format(
                    _METRIC_NAME_PREFIX, _VGPU_METRIC_NAME_PREFIX, measurement)
                self.gauge(metric_name,
                           value,
                           device_name=vgpu_metrics.get('name'),
                           dimensions=vgpu_metrics.get('dimensions'),
                           value_meta=None)
            log.debug('Collected info for vGPU {}'.format(
                vgpu_metrics.get('name')))
