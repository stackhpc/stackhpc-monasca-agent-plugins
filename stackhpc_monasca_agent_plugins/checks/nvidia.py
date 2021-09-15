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
from py3nvml import py3nvml as pynvml
import stackhpc_monasca_agent_plugins.checks.nvidiasmi as nvidiasmi


log = logging.getLogger(__name__)

_METRIC_NAME_PREFIX = "nvidia"
_VGPU_METRIC_NAME_PREFIX = "vgpu"


class Nvidia(checks.AgentCheck):
    def __init__(self, name, init_config, agent_config):
        super(Nvidia, self).__init__(name, init_config, agent_config)

    def handle_not_supported(f):
        def wrapper(*args, **kw):
            try:
                return f(*args, **kw)
            except pynvml.NVMLError as err:
                if err == pynvml.NVMLError(pynvml.NVML_ERROR_NOT_SUPPORTED):
                    log.info('Not supported: {}'.format(f.__name__))
                    return {}
                else:
                    raise
        return wrapper

    @staticmethod
    @handle_not_supported
    def _get_driver_version():
        return {'driver_version': pynvml.nvmlSystemGetDriverVersion()}

    @staticmethod
    @handle_not_supported
    def _get_fan_speed_percent(gpu):
        return {'fan_speed_percent': pynvml.nvmlDeviceGetFanSpeed(gpu)}

    @staticmethod
    @handle_not_supported
    def _get_device_name(gpu):
        return {'name': pynvml.nvmlDeviceGetName(gpu)}

    @staticmethod
    @handle_not_supported
    def _get_device_serial(gpu):
        return {'serial': pynvml.nvmlDeviceGetSerial(gpu)}

    @staticmethod
    @handle_not_supported
    def _get_device_uuid(gpu):
        return {'uuid': pynvml.nvmlDeviceGetUUID(gpu)}

    @staticmethod
    @handle_not_supported
    def _get_device_vbios_version(gpu):
        return {'vbios_version': pynvml.nvmlDeviceGetVbiosVersion(gpu)}

    @staticmethod
    @handle_not_supported
    def _get_info_rom_image_version(gpu):
        return {'info_rom_image_version':
                pynvml.nvmlDeviceGetInforomImageVersion(gpu)}

    @staticmethod
    @handle_not_supported
    def _get_device_power_state(gpu):
        power_state = "P{}".format(pynvml.nvmlDeviceGetPowerState(gpu))
        return {'power_state': power_state}

    @staticmethod
    @handle_not_supported
    def _get_framebuffer_memory_stats(gpu):
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(gpu)
        return {
            'memory_fb_total_bytes': mem_info.total,
            'memory_fb_used_bytes': mem_info.used,
            'memory_fb_free_bytes': (mem_info.total - mem_info.used)
        }

    @staticmethod
    @handle_not_supported
    def _get_bar1_memory_stats(gpu):
        mem_info = pynvml.nvmlDeviceGetBAR1MemoryInfo(gpu)
        return {
            'memory_bar1_total_bytes': mem_info.bar1Total,
            'memory_bar1_used_bytes': mem_info.bar1Used,
            'memory_bar1_free_bytes': (mem_info.bar1Total - mem_info.bar1Used)
        }

    @staticmethod
    @handle_not_supported
    def _get_utilisation_stats(gpu):
        util = pynvml.nvmlDeviceGetUtilizationRates(gpu)
        return {
            'utilisation_gpu_percent': util.gpu,
            'utilisation_memory_percent': util.memory
        }

    @staticmethod
    @handle_not_supported
    def _get_device_temperature(gpu):
        return {'temperature_deg_c':
                pynvml.nvmlDeviceGetTemperature(
                    gpu, pynvml.NVML_TEMPERATURE_GPU)}

    @staticmethod
    @handle_not_supported
    def _get_device_shutdown_temp(gpu):
        return {'temperature_shutdown_deg_c':
                pynvml.nvmlDeviceGetTemperatureThreshold(
                    gpu, pynvml.NVML_TEMPERATURE_THRESHOLD_SHUTDOWN)}

    @staticmethod
    @handle_not_supported
    def _get_device_slowdown_temp(gpu):
        return {'temperature_slowdown_deg_c':
                pynvml.nvmlDeviceGetTemperatureThreshold(
                    gpu, pynvml.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN)}

    @staticmethod
    @handle_not_supported
    def _get_power_usage_watts(gpu):
        return {'power_watts': (pynvml.nvmlDeviceGetPowerUsage(gpu) / 1000.0)}

    @staticmethod
    @handle_not_supported
    def _get_power_limit_watts(gpu):
        return {'power_limit_watts': (
            pynvml.nvmlDeviceGetPowerManagementLimit(gpu) / 1000.0)}

    @staticmethod
    @handle_not_supported
    def _get_clock_info(gpu):
        return {
            'clock_freq_gpu_mhz':
                pynvml.nvmlDeviceGetClockInfo(gpu, pynvml.NVML_CLOCK_GRAPHICS),
            'clock_freq_sm_mhz':
                pynvml.nvmlDeviceGetClockInfo(gpu, pynvml.NVML_CLOCK_SM),
            'clock_freq_memory_mhz':
                pynvml.nvmlDeviceGetClockInfo(gpu, pynvml.NVML_CLOCK_MEM),
            'clock_freq_video_mhz':
                pynvml.nvmlDeviceGetClockInfo(gpu, pynvml.NVML_CLOCK_VIDEO)
        }

    @staticmethod
    @handle_not_supported
    def _get_clock_max_info(gpu):
        return {
            'clock_max_freq_gpu_mhz':
                pynvml.nvmlDeviceGetMaxClockInfo(
                    gpu, pynvml.NVML_CLOCK_GRAPHICS),
            'clock_max_freq_sm_mhz':
                pynvml.nvmlDeviceGetMaxClockInfo(gpu, pynvml.NVML_CLOCK_SM),
            'clock_max_freq_memory_mhz':
                pynvml.nvmlDeviceGetMaxClockInfo(gpu, pynvml.NVML_CLOCK_MEM),
            'clock_max_freq_video_mhz':
                pynvml.nvmlDeviceGetMaxClockInfo(gpu, pynvml.NVML_CLOCK_VIDEO)
        }

    @staticmethod
    def _get_gpu_info():
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        all_info = []
        for i in range(0, deviceCount):
            gpu = pynvml.nvmlDeviceGetHandleByIndex(i)

            dimensions = {}
            dimensions.update(Nvidia._get_driver_version())
            dimensions.update(Nvidia._get_device_uuid(gpu))
            dimensions.update(Nvidia._get_info_rom_image_version(gpu))
            dimensions.update(Nvidia._get_device_power_state(gpu))
            dimensions.update(Nvidia._get_device_vbios_version(gpu))

            measurements = {}
            measurements.update(Nvidia._get_fan_speed_percent(gpu))
            measurements.update(Nvidia._get_framebuffer_memory_stats(gpu))
            measurements.update(Nvidia._get_bar1_memory_stats(gpu))
            measurements.update(Nvidia._get_utilisation_stats(gpu))
            measurements.update(Nvidia._get_device_temperature(gpu))
            measurements.update(Nvidia._get_device_shutdown_temp(gpu))
            measurements.update(Nvidia._get_device_slowdown_temp(gpu))
            measurements.update(Nvidia._get_power_usage_watts(gpu))
            measurements.update(Nvidia._get_power_limit_watts(gpu))
            measurements.update(Nvidia._get_clock_info(gpu))
            measurements.update(Nvidia._get_clock_max_info(gpu))

            gpu_name = "{}_{}".format(
                Nvidia._get_device_name(gpu).get('name'),
                Nvidia._get_device_serial(gpu).get('serial'))
            gpu_info = {
                'name': gpu_name,
                'dimensions': dimensions,
                'measurements': measurements
            }
            all_info.append(gpu_info)
        pynvml.nvmlShutdown()
        return all_info

    @staticmethod
    def _get_vgpu_info():
        cnsmi = nvidiasmi.Nvidiasmi()
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
        for gpu_metrics in Nvidia._get_gpu_info():
            for measurement, value in gpu_metrics['measurements'].items():
                metric_name = '{0}.{1}'.format(
                    _METRIC_NAME_PREFIX, measurement)
                self.gauge(metric_name,
                           value,
                           device_name=gpu_metrics.get('name'),
                           dimensions=gpu_metrics.get('dimensions'),
                           value_meta=None)
            log.debug('Collected info for GPU {}'.format(
                gpu_metrics.get('name')))


        for vgpu_metrics in Nvidia._get_vgpu_info():
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
