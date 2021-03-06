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

import monasca_setup.agent_config
import monasca_setup.detection

LOG = logging.getLogger(__name__)

_SCONTROL_PATH = "/usr/bin/scontrol"


class SlurmDetect(monasca_setup.detection.Plugin):
    """Detects and configures Slurm plugin."""

    def _detect(self):
        self.available = False
        if not self._detect_slurm():
            LOG.info('Slurm scontrol was not detected: slurm plugin'
                     'will not be loaded.')
            return
        self.available = True

    def build_config(self):
        config = monasca_setup.agent_config.Plugins()
        config['slurm'] = {
            'init_config': None,
            'instances': [{'name': 'slurm_stats'}]}
        return config

    def _detect_slurm(self):
        return os.path.exists(_SCONTROL_PATH)
