import json
import logging
import traceback
from typing import Optional

import yaml
from ops.manifests import ConfigRegistry, ManifestLabel, Manifests, Patch

log = logging.getLogger()


class RemoveNamespace(Patch):
    """Remove namespace from resources so they deploy to the charm's namespace"""

    def __call__(self, obj):
        obj.metadata.namespace = None


class ResourceListConfigError(Exception):
    """Raised when the resource-list charm config is invalid"""

    pass


class SetCommandLineArgs(Patch):
    """Set sriovdp's command line args"""

    def __call__(self, obj):
        if obj.kind != "DaemonSet" or not obj.metadata.name.startswith(
            "kube-sriov-device-plugin-"
        ):
            return
        args_to_set = {
            "--log-level": self.manifests.config["log-level"],
            "--resource-prefix": self.manifests.config["resource-prefix"],
        }
        for container in obj.spec.template.spec.containers:
            if container.name != "kube-sriovdp":
                continue
            filtered_args = [
                arg for arg in container.args if arg.split("=")[0] not in args_to_set
            ]
            container.args = filtered_args + [
                f"{key}={value}" for key, value in args_to_set.items()
            ]


class SetConfigMapData(Patch):
    """Set the sriovdp-config ConfigMap's resourceList config"""

    def __call__(self, obj):
        if obj.kind != "ConfigMap" or obj.metadata.name != "sriovdp-config":
            return
        obj.data["config.json"] = json.dumps(
            {"resourceList": self.manifests.config["resource-list"]}, indent=2
        )


class SRIOVNetworkDevicePluginManifests(Manifests):
    def __init__(self, charm, charm_config):
        manipulations = [
            ConfigRegistry(self),
            ManifestLabel(self),
            RemoveNamespace(self),
            SetCommandLineArgs(self),
            SetConfigMapData(self),
        ]
        super().__init__(
            "sriov-network-device-plugin", charm.model, "upstream", manipulations
        )
        self.charm_config = charm_config

    def get_resource_list(self, check=True):
        resource_list_str = self.charm_config.get("resource-list", "[]")
        resource_list = []
        try:
            resource_list = yaml.safe_load(resource_list_str)
            if check and not resource_list:
                raise ResourceListConfigError("resource-list config must be specified")
        except yaml.YAMLError:
            log.error(traceback.format_exc())
            if check:
                raise ResourceListConfigError(
                    "resource-list config is invalid, see debug-log"
                )
        return resource_list

    @property
    def config(self):
        return {
            "image-registry": self.charm_config["image-registry"],
            "log-level": self.charm_config.get("log-level", 10),
            "release": None,
            "resource-list": self.get_resource_list(check=False),
            "resource-prefix": self.charm_config.get("resource-prefix", "intel.com"),
        }

    @property
    def error(self) -> Optional[str]:
        try:
            self.get_resource_list()
        except ResourceListConfigError as e:
            return str(e)
