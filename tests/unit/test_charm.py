# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest.mock as mock

import ops.testing
import pytest
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charm import SRIOVNetworkDevicePluginCharm

RESOURCE_LIST = '{"resourceName": "test", "selectors": {"drivers": ["ixgbevf"]}}'
RESOURCE_LIST_INVALID = "["
RESOURCE_LIST_MISSING = "[]"


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
        "Versions: sriov-network-device-plugin=v3.5.1"
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
