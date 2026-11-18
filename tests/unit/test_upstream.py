"""Exercise real bundles and the upstream-to-charm upgrade transformation."""

import json
from pathlib import Path

import ops.testing
import pytest
import yaml

from charm import SRIOVNetworkDevicePluginCharm
from manifests import SRIOVNetworkDevicePluginManifests
from upstream.update import ARCHITECTURES, daemonsets_for_upgrade

BUNDLES = Path("upstream/manifests")
RELEASES = sorted(
    (path.name for path in BUNDLES.iterdir() if path.is_dir()),
    key=lambda version: tuple(int(part) for part in version.lstrip("v").split(".")),
)
RESOURCE_LIST = [{"resourceName": "test", "selectors": {"drivers": ["ixgbevf"]}}]


def load_daemonsets(release):
    with (BUNDLES / release / "sriovdp-daemonset.yaml").open() as stream:
        return {
            obj["metadata"]["name"]: obj
            for obj in yaml.safe_load_all(stream)
            if obj["kind"] == "DaemonSet"
        }


@pytest.mark.parametrize("release", RELEASES)
def test_render_bundles_and_preserve_upgrade_identity(release):
    harness = ops.testing.Harness(SRIOVNetworkDevicePluginCharm)
    try:
        harness.begin()
        manifests = SRIOVNetworkDevicePluginManifests(
            harness.charm,
            {
                "image-registry": "registry.example/mirror",
                "log-level": 3,
                "resource-prefix": "example.com",
                "resource-list": yaml.safe_dump(RESOURCE_LIST),
            },
        )
        original = load_daemonsets(RELEASES[0])
        # Exercise the authoritative default lookup as well as each bundled release.
        assert manifests.current_release in RELEASES
        assert list(manifests.resources)
        manifests.default_release = release
        resources = [obj.resource for obj in manifests.resources]
        daemonsets = [obj for obj in resources if obj.kind == "DaemonSet"]
        assert {obj.metadata.name for obj in daemonsets} == set(original)
        for architecture in ARCHITECTURES:
            scheduled = [
                obj
                for obj in daemonsets
                if architecture in obj.spec.template.spec.nodeSelector.values()
            ]
            assert len(scheduled) == 1
            obj = scheduled[0]
            assert (
                obj.spec.selector.to_dict()
                == original[obj.metadata.name]["spec"]["selector"]
            )
            assert all(
                obj.spec.template.metadata.labels[key] == value
                for key, value in obj.spec.selector.matchLabels.items()
            )
            spec = obj.spec.template.spec
            assert spec.hostNetwork
            assert spec.serviceAccountName == "sriov-device-plugin"
            container = spec.containers[0]
            assert container.securityContext.privileged
            assert container.image.startswith("registry.example/mirror/")
            assert "latest" not in container.image
            assert "--resource-prefix=example.com" in container.args
            assert "--log-level=3" in container.args
            assert "node-role.kubernetes.io/control-plane" in {
                toleration.key for toleration in spec.tolerations
            }
            assert {mount.name for mount in container.volumeMounts} == {
                volume.name for volume in spec.volumes
            }
        config = next(obj for obj in resources if obj.kind == "ConfigMap")
        assert json.loads(config.data["config.json"]) == {"resourceList": RESOURCE_LIST}
        assert all(obj.metadata.namespace is None for obj in resources)
    finally:
        harness.cleanup()


def test_expand_unsuffixed_upstream_daemonset():
    # Use a real released bundle as the fixture for upstream's unified shape.
    release = RELEASES[-1]
    source = next(iter(load_daemonsets(release).values()))
    source["metadata"]["name"] = "kube-sriov-device-plugin"
    spec = source["spec"]["template"]["spec"]
    spec.pop("nodeSelector")
    spec.pop("tolerations", None)
    spec["containers"][0]["image"] = "ghcr.io/example/device-plugin:latest"
    selector = source["spec"]["selector"]

    expanded = daemonsets_for_upgrade([source], release)

    assert source["metadata"]["name"] == "kube-sriov-device-plugin"
    assert len(expanded) == len(ARCHITECTURES)
    for obj, architecture in zip(expanded, ARCHITECTURES):
        assert obj["metadata"]["name"] == f"kube-sriov-device-plugin-{architecture}"
        assert obj["spec"]["selector"] == selector
        assert obj["spec"]["template"]["spec"]["nodeSelector"] == {
            "kubernetes.io/arch": architecture
        }
        assert obj["spec"]["template"]["spec"]["volumes"] == spec["volumes"]
        assert obj["spec"]["template"]["spec"]["containers"][0]["image"] == (
            f"ghcr.io/example/device-plugin:{release}"
        )
