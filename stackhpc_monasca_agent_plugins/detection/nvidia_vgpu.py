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
import subprocess

import monasca_setup.agent_config
import monasca_setup.detection

log = logging.getLogger(__name__)

# Directory to use for instance and metric caches (preferred tmpfs "/dev/shm")
cache_dir = "/dev/shm"
# Maximum age of instance cache before automatic refresh (in seconds)
nova_refresh = 60 * 60 * 4  # Four hours
# List of instance metadata keys to be sent as dimensions
# By default 'scale_group' metadata is used here for supporting auto
# scaling in Heat.
metadata = ['scale_group']


class NvidiaVgpuDetect(monasca_setup.detection.Plugin):
    """Detects and configures nVidia plugin."""
    @staticmethod
    def _has_cache_dir():
        return os.path.isdir(cache_dir)

    def _get_init_config(self):
        init_config = {
            'cache_dir': cache_dir,
            'nova_refresh': nova_refresh,
            'metadata': metadata
        }
        return init_config

    def _detect(self):
        self.available = False
        if b'nvidia' not in subprocess.check_output(
                ["lshw", "-C", "display"]).lower():
            log.info('No nVidia hardware detected.')
            return
        self.available = self._has_cache_dir()

    def build_config(self):
        """Build the config as a Plugins object and return back.
        """
        config = monasca_setup.agent_config.Plugins()
        init_config = self._get_init_config()
        if self.args:
            for arg in self.args:
                init_config[arg] = self.literal_eval(self.args[arg])

        config['nvidia_vgpu'] = {
            'init_config': init_config,
            'instances': [{'name': 'nvidia_stats'}]}

        return config
