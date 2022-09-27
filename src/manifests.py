import json
import logging
import traceback

import yaml
from ops.manifests import ConfigRegistry, ManifestLabel, Manifests, Patch

log = logging.getLogger()


class RemoveNamespace(Patch):
    """Remove namespace from resources so they deploy to the local namespace"""

    def __call__(self, obj):
        obj.metadata.namespace = None


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

    @property
    def config(self):
        log_level = self.charm_config.get("log-level", 10)
        resource_prefix = self.charm_config.get("resource-prefix", "intel.com")
        resource_list_str = self.charm_config.get("resource-list", "[]")
        error = None
        try:
            resource_list = yaml.safe_load(resource_list_str)
            if not resource_list:
                error = "resource-list config must be specified"
        except yaml.YAMLError:
            log.error(traceback.format_exc())
            resource_list = []
            error = "resource-list config is invalid, see debug-log"

        return {
            "error": error,
            "image-registry": self.charm_config["image-registry"],
            "log-level": log_level,
            "release": None,
            "resource-list": resource_list,
            "resource-prefix": resource_prefix,
        }
