# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest.mock as mock
from pathlib import Path

import ops.testing
import pytest
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charm import SRIOVNetworkDevicePluginCharm
from manifests import SRIOVNetworkDevicePluginManifests

RESOURCE_LIST = '{"resourceName": "test", "selectors": {"drivers": ["ixgbevf"]}}'
RESOURCE_LIST_INVALID = "["
RESOURCE_LIST_MISSING = "[]"
# Default release shipped before the CK 1.36 onboarding.
PREVIOUS_DEFAULT = "v3.5.1"


@pytest.fixture
def harness():
    harness = ops.testing.Harness(SRIOVNetworkDevicePluginCharm)
    try:
        harness.begin()
        harness.set_leader(True)
        yield harness
    finally:
        harness.cleanup()


@mock.patch("charm.Collector.unready", new=[])
@mock.patch("charm.SRIOVNetworkDevicePluginManifests.apply_manifests")
def test_config_ready(mock_apply_manifests, harness):
    harness.update_config({"resource-list": RESOURCE_LIST})
    mock_apply_manifests.assert_called_once_with()
    assert harness.charm.unit.status == ActiveStatus()
    assert harness.charm.app.status == ActiveStatus(
        "Versions: sriov-network-device-plugin=v3.11.0"
    )


@mock.patch("charm.Collector.unready", new=["sriovdp is not ready"])
@mock.patch("charm.SRIOVNetworkDevicePluginManifests.apply_manifests")
def test_config_unready(mock_apply_manifests, harness):
    harness.update_config({"resource-list": RESOURCE_LIST})
    mock_apply_manifests.assert_called_once_with()
    assert harness.charm.unit.status == WaitingStatus("sriovdp is not ready")


@mock.patch("charm.SRIOVNetworkDevicePluginManifests.apply_manifests")
def test_config_invalid(mock_apply_manifests, harness):
    harness.update_config({"resource-list": RESOURCE_LIST_INVALID})
    mock_apply_manifests.assert_not_called()
    assert harness.charm.unit.status == BlockedStatus(
        "resource-list config is invalid, see debug-log"
    )


@mock.patch("charm.SRIOVNetworkDevicePluginManifests.apply_manifests")
def test_config_missing(mock_apply_manifests, harness):
    harness.update_config({"resource-list": RESOURCE_LIST_MISSING})
    mock_apply_manifests.assert_not_called()
    assert harness.charm.unit.status == BlockedStatus(
        "resource-list config must be specified"
    )


def _applied_daemonset_images(apply_resources):
    (resources,) = [call.args for call in apply_resources.call_args_list]
    return {
        rsc.resource.metadata.name: [
            container.image for container in rsc.resource.spec.template.spec.containers
        ]
        for rsc in resources
        if rsc.resource.kind == "DaemonSet"
    }


@mock.patch("charm.Collector.unready", new=[])
@mock.patch.object(SRIOVNetworkDevicePluginManifests, "apply_resources")
def test_refresh_applies_new_default_release(apply_resources, harness):
    """A refresh with unchanged config must roll out the new bundled default.

    The charm has no release option: upstream/version is the default and
    config-changed, which Juju runs after upgrade-charm, always re-applies.
    """
    default = Path("upstream/version").read_text().strip()
    assert default != PREVIOUS_DEFAULT

    # Deployed by the previous charm revision, whose default was PREVIOUS_DEFAULT.
    with mock.patch.object(
        SRIOVNetworkDevicePluginManifests, "default_release", PREVIOUS_DEFAULT
    ):
        harness.update_config({"resource-list": RESOURCE_LIST})
    before = _applied_daemonset_images(apply_resources)
    assert all(
        f":{PREVIOUS_DEFAULT}" in image
        for images in before.values()
        for image in images
    )

    # juju refresh: upgrade-charm followed by config-changed, config unchanged.
    apply_resources.reset_mock()
    harness.charm.on.upgrade_charm.emit()
    harness.charm.on.config_changed.emit()
    after = _applied_daemonset_images(apply_resources)

    assert after.keys() == before.keys()
    assert all(
        image.endswith(f":{default}") for images in after.values() for image in images
    )
    assert harness.charm.app.status == ActiveStatus(
        f"Versions: sriov-network-device-plugin={default}"
    )
