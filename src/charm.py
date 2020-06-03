#!/usr/bin/env python3

import json
import logging
from oci_image import OCIImageResource, OCIImageResourceError
from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
import traceback
import yaml


log = logging.getLogger()


class SRIOVNetworkDevicePluginCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.image = OCIImageResource(self,
                                      'sriov-network-device-plugin-image')
        self.framework.observe(self.on.install, self.set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self.set_pod_spec)
        self.framework.observe(self.on.config_changed, self.set_pod_spec)

    def set_pod_spec(self, event):
        if not self.model.unit.is_leader():
            log.info('Not a leader, skipping set_pod_spec')
            self.model.unit.status = ActiveStatus()
            return

        try:
            image_details = self.image.fetch()
        except OCIImageResourceError as e:
            self.model.unit.status = e.status
            return

        log_level = self.model.config.get('log-level', 10)
        resource_prefix = self.model.config.get('resource-prefix', 'intel.com')
        resource_list_str = self.model.config.get('resource-list', '[]')
        try:
            resource_list = yaml.safe_load(resource_list_str)
        except yaml.YAMLError:
            log.error(traceback.format_exc())
            msg = 'resource-list config is invalid, see debug-log'
            self.model.unit.status = BlockedStatus(msg)
            return
        if not resource_list:
            msg = 'resource-list config must be specified'
            self.model.unit.status = BlockedStatus(msg)
            return

        device_plugin_config = {
            'resourceList': resource_list
        }

        self.model.unit.status = MaintenanceStatus('Setting pod spec')
        self.model.pod.set_spec({
            'version': 3,
            'containers': [{
                'name': 'kube-sriovdp',
                'imageDetails': image_details,
                'args': [
                    '--log-dir=sriovdp',
                    '--log-level=' + str(log_level),
                    '--resource-prefix=' + resource_prefix,
                ],
                'kubernetes': {
                    'securityContext': {
                        'privileged': True
                    }
                },
                'volumeConfig': [
                    {
                        'name': 'devicesock',
                        'mountPath': '/var/lib/kubelet/',
                        'hostPath': {
                            'path': '/var/lib/kubelet/'
                        }
                    },
                    {
                        'name': 'log',
                        'mountPath': '/var/log',
                        'hostPath': {
                            'path': '/var/log'
                        }
                    },
                    {
                        'name': 'config-volume',
                        'mountPath': '/etc/pcidp',
                        'files': [{
                            'path': 'config.json',
                            'content': json.dumps(device_plugin_config)
                        }]
                    }
                ]
            }],
            'kubernetesResources': {
                'pod': {
                    'hostNetwork': True,
                    # FIXME: use hostPID once it is available in Juju
                    # https://bugs.launchpad.net/juju/+bug/1883934
                    # 'hostPID': True
                }
            }
        })
        self.model.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(SRIOVNetworkDevicePluginCharm)
