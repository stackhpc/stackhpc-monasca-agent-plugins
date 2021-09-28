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
import os
import stat

import monasca_agent.collector.checks as checks
import monasca_agent.collector.checks.utils as utils
from monasca_agent.common import keystone
from monasca_agent import version as ma_version
from novaclient import client as n_client
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
        return {'vgpu_uuid': cls.vgpu_info[index].get("vGPU UUID")}

    @classmethod
    def get_vgpu_name(cls, index):
        return {'name': cls.vgpu_info[index].get("vGPU Name")}

    @classmethod
    def get_vgpu_vm_uuid(cls, index):
        return {'vm_uuid': cls.vgpu_info[index].get("VM UUID")}

    @classmethod
    def get_vgpu_vm_name(cls, index):
        return {'vm_name': cls.vgpu_info[index].get("VM Name")}


class NvidiaVgpu(checks.AgentCheck):
    def __init__(self, name, init_config, agent_config):
        super(Nvidia, self).__init__(name, init_config, agent_config)

        self.instance_cache_file = "{0}/{1}".format(self.init_config.get('cache_dir'),
                                                    'vgpu_instances.json')

    def _load_instance_cache(self):
        """Load the cache map of instance names to Nova data.
           If the cache does not yet exist or is damaged, (re-)build it.
        """
        instance_cache = {}
        try:
            with open(self.instance_cache_file, 'r') as cache_json:
                instance_cache = json.load(cache_json)

                # Is it time to force a refresh of this data?
                if self.init_config.get('nova_refresh') is not None:
                    time_diff = time.time() - instance_cache['last_update']
                    if time_diff > self.init_config.get('nova_refresh'):
                        self._update_instance_cache()
        except (IOError, TypeError, ValueError):
            # The file may not exist yet, or is corrupt.  Rebuild it now.
            self.log.warning("Instance cache missing or corrupt, rebuilding.")
            instance_cache = self._update_instance_cache()
            pass

        return instance_cache

    def _get_nova_host(self, nova_client):
        if not self._nova_host:
            # Find `nova-compute` on current node
            services = nova_client.services.list(host=self.hostname,
                                                 binary='nova-compute')
            if not services:
                # Catch the case when `nova-compute` is registered with
                # unqualified hostname
                services = nova_client.services.list(
                    host=self.hostname.split('.')[0], binary='nova-compute')
            if services:
                self._nova_host = services[0].host
                self.log.info("Found 'nova-compute' registered with host: {}"
                              .format(self._nova_host))

        if self._nova_host:
            return self._nova_host
        else:
            self.log.warn("No 'nova-compute' service found on host: {}"
                          .format(self.hostname))
            # Return hostname as fallback value
            return self.hostname

    def _update_instance_cache(self):
        """Collect instance_id, project_id, and AZ for all instance UUIDs
        """

        id_cache = {}
        flavor_cache = {}
        port_cache = None
        netns = None
        # Get a list of all instances from the Nova API
        session = keystone.get_session(**self.init_config)
        nova_client = n_client.Client(
            "2.1", session=session,
            endpoint_type=self.init_config.get("endpoint_type", "publicURL"),
            service_type="compute",
            region_name=self.init_config.get('region_name'),
            client_name='monasca-agent[nvidiavgpu]',
            client_version=ma_version.version_string)
        instances = nova_client.servers.list(
            search_opts={'all_tenants': 1,
                         'host': self._get_nova_host(nova_client)})
        for instance in instances:
            instance_ports = []
            inst_id = instance.id
            inst_az = instance.__getattr__('OS-EXT-AZ:availability_zone')
            id_cache[inst_id] = {'instance_uuid': instance.id,
                                 'hostname': instance.name,
                                 'zone': inst_az,
                                 'created': instance.created,
                                 'tenant_id': instance.tenant_id}

            for config_var in ['metadata', 'customer_metadata']:
                if self.init_config.get(config_var):
                    for metadata in self.init_config.get(config_var):
                        if instance.metadata.get(metadata):
                            id_cache[inst_id][metadata] = (instance.metadata.
                                                             get(metadata))

        id_cache['last_update'] = int(time.time())

        # Write the updated cache
        try:
            with open(self.instance_cache_file, 'w') as cache_json:
                json.dump(id_cache, cache_json)
            if stat.S_IMODE(os.stat(self.instance_cache_file).st_mode) != 0o600:
                os.chmod(self.instance_cache_file, 0o600)
        except IOError as e:
            self.log.error("Cannot write to {0}: {1}".format(self.instance_cache_file, e))

        return id_cache

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
        """Gather vgpu metrics for each instance"""

        instance_cache = self._load_instance_cache()

        for vgpu_metrics in NvidiaVgpu._get_vgpu_info():
            inst_id = vgpu_metrics.get('dimensions')['vm_uuid']
            # If new instances are detected, update the instance cache
            if inst_id not in instance_cache:
                instance_cache = self._update_instance_cache()

            dimensions=vgpu_metrics.get('dimensions')
            dimensions.update({'hostname': instance_cache.get(inst_id)['hostname']})
            for measurement, value in vgpu_metrics['measurements'].items():
                metric_name = '{0}.{1}.{2}'.format(
                    _METRIC_NAME_PREFIX, _VGPU_METRIC_NAME_PREFIX, measurement)
                self.gauge(metric_name,
                           value,
                           device_name=vgpu_metrics.get('name'),
                           dimensions=vgpu_metrics.get('dimensions'),
                           delegated_tenant=instance_cache.get(inst_id)['tenant_id'],
                           value_meta=None)
            log.debug('Collected info for vGPU {}'.format(
                vgpu_metrics.get('name')))
