# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import json
import unittest.mock as mock

import ops.testing
import pytest

from charm import SRIOVNetworkDevicePluginCharm
from manifests import (
    RemoveNamespace,
    SetCommandLineArgs,
    SetConfigMapData,
    UpdateDaemonSetTolerations,
)


@pytest.fixture
def harness():
    harness = ops.testing.Harness(SRIOVNetworkDevicePluginCharm)
    try:
        harness.begin()
        harness.set_leader(True)
        yield harness
    finally:
        harness.cleanup()


def test_remove_namespace(harness):
    patch = RemoveNamespace(harness.charm.manifests)
    obj = mock.MagicMock()
    obj.metadata.namespace = "kube-system"
    patch(obj)
    assert obj.metadata.namespace is None


def test_update_tolerations(harness):
    patch = UpdateDaemonSetTolerations(harness.charm.manifests)
    toleration = mock.MagicMock()
    toleration.key = "node-role.kubernetes.io/important"
    toleration.operator = "Exists"
    toleration.effect = "NoSchedule"

    obj = mock.MagicMock()
    obj.kind = "DaemonSet"
    obj.metadata.name = "kube-sriov-device-plugin-amd64"
    obj.spec.template.spec.tolerations = [toleration]
    patch(obj)
    assert len(obj.spec.template.spec.tolerations) == 2
    assert all(
        t.key.endswith(("control-plane", "important"))
        for t in obj.spec.template.spec.tolerations
    )


def test_update_tolerations_only_changes_recognized_daemonset(
    harness,
):
    patch = UpdateDaemonSetTolerations(harness.charm.manifests)
    obj = mock.Mock(kind="DaemonSet", **{"metadata.name": "not-sriovdp"})
    patch(obj)
    # Mock object would raise a TypeError
    # if any attempt to access the spec is attempted


def test_set_command_line_args(harness):
    patch = SetCommandLineArgs(harness.charm.manifests)
    container = mock.MagicMock()
    container.name = "kube-sriovdp"
    container.args = ["--log-dir=sriovdp", "--log-level=10"]
    obj = mock.MagicMock()
    obj.kind = "DaemonSet"
    obj.metadata.name = "kube-sriov-device-plugin-amd64"
    obj.spec.template.spec.containers = [container]
    patch(obj)
    assert container.args == [
        "--log-dir=sriovdp",
        "--log-level=10",
        "--resource-prefix=intel.com",
    ]


@pytest.mark.parametrize(
    "kind,name,container_name",
    [
        ("DaemonSet", "not-sriovdp", "kube-sriovdp"),
        ("Deployment", "kube-sriov-device-plugin-amd64", "kube-sriovdp"),
        ("DaemonSet", "kube-sriov-device-plugin-amd64", "not-sriovdp"),
    ],
)
def test_set_command_line_args_only_changes_recognized_daemonset(
    harness, kind, name, container_name
):
    patch = SetCommandLineArgs(harness.charm.manifests)
    container = mock.MagicMock()
    container.name = container_name
    container.args = ["--log-dir=sriovdp", "--log-level=10"]
    obj = mock.MagicMock()
    obj.kind = kind
    obj.metadata.name = name
    obj.spec.template.spec.containers = [container]
    patch(obj)
    assert container.args == ["--log-dir=sriovdp", "--log-level=10"]


def test_set_config_map_data(harness):
    patch = SetConfigMapData(harness.charm.manifests)
    obj = mock.MagicMock()
    obj.kind = "ConfigMap"
    obj.metadata.name = "sriovdp-config"
    obj.data = {}
    patch(obj)
    assert json.loads(obj.data["config.json"]) == {"resourceList": []}


@pytest.mark.parametrize(
    "kind,name", [("Secret", "sriovdp-config"), ("ConfigMap", "not-sriovdp")]
)
def test_set_config_map_data_only_changes_recognized_config_map(harness, kind, name):
    patch = SetConfigMapData(harness.charm.manifests)
    obj = mock.MagicMock()
    obj.kind = kind
    obj.metadata.name = name
    obj.data = {}
    patch(obj)
    assert obj.data == {}
