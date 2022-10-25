import logging
import os
import shlex
from pathlib import Path
from random import choices
from string import ascii_lowercase, digits

import juju.utils
import pytest
import yaml
from pytest_operator.plugin import OpsTest

log = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption(
        "--k8s-cloud",
        action="store",
        help="Juju kubernetes cloud to reuse; if not provided, will generate a new cloud",
    )
    parser.addoption(
        "--k8s-model",
        action="store",
        help="Juju kubernetes model to reuse; if not provided, will generate a new model",
    )


@pytest.fixture(scope="module")
async def charmed_kubernetes(ops_test):
    overlays = [
        ops_test.Bundle("kubernetes-core", channel="edge"),
        "tests/data/k8s-overlay.yaml",
    ]

    log.info("Rendering overlays...")
    bundle, *overlays = await ops_test.async_render_bundles(*overlays)

    log.info("Deploying k8s-core...")
    model = ops_test.model_full_name
    juju_cmd = f"deploy -m {model} {bundle} --trust " + " ".join(
        f"--overlay={f}" for f in overlays
    )

    await ops_test.juju(*shlex.split(juju_cmd), fail_msg="Bundle deploy failed")

    await ops_test.model.wait_for_idle(status="active", timeout=60 * 60)


@pytest.fixture(scope="module")
async def kubeconfig(ops_test, charmed_kubernetes):
    kubeconfig_path = ops_test.tmp_path / "kubeconfig"
    rc, stdout, stderr = await ops_test.run(
        "juju",
        "scp",
        "kubernetes-control-plane/leader:/home/ubuntu/config",
        kubeconfig_path,
    )
    if rc != 0:
        log.error(f"retcode: {rc}")
        log.error(f"stdout:\n{stdout.strip()}")
        log.error(f"stderr:\n{stderr.strip()}")
        pytest.fail("Failed to copy kubeconfig from kubernetes-control-plane")
    assert Path(kubeconfig_path).stat().st_size, "kubeconfig file is 0 bytes"
    yield kubeconfig_path


@pytest.fixture(scope="module")
def module_name(request):
    return request.module.__name__.replace("_", "-")


@pytest.fixture(scope="module")
async def k8s_cloud(kubeconfig, module_name, ops_test, request):
    """Use an existing k8s-cloud or create a k8s-cloud
    for deploying a new k8s model into"""
    cloud_name = request.config.option.k8s_cloud or f"{module_name}-k8s-cloud"
    controller = await ops_test.model.get_controller()
    try:
        current_clouds = await controller.clouds()
        if f"cloud-{cloud_name}" in current_clouds.clouds:
            yield cloud_name
            return
    finally:
        await controller.disconnect()

    with ops_test.model_context("main"):
        log.info(f"Adding cloud '{cloud_name}'...")
        os.environ["KUBECONFIG"] = str(kubeconfig)
        await ops_test.juju(
            "add-k8s",
            cloud_name,
            f"--controller={ops_test.controller_name}",
            "--skip-storage",
            check=True,
            fail_msg=f"Failed to add-k8s {cloud_name}",
        )
    yield cloud_name

    with ops_test.model_context("main"):
        if not ops_test.keep_model:
            log.info(f"Removing cloud '{cloud_name}'...")
            await ops_test.juju(
                "remove-cloud",
                cloud_name,
                "--controller",
                ops_test.controller_name,
                check=True,
            )


@pytest.fixture(scope="module")
async def k8s_model(k8s_cloud, ops_test: OpsTest, request):
    model_alias = "k8s-model"
    log.info("Creating k8s model ...")
    # Create model with Juju CLI to work around a python-libjuju bug
    # https://github.com/juju/python-libjuju/issues/603
    model_name = request.config.option.k8s_model or (
        "test-sriovdp-" + "".join(choices(ascii_lowercase + digits, k=4))
    )
    await ops_test.juju(
        "add-model",
        f"--controller={ops_test.controller_name}",
        model_name,
        k8s_cloud,
        "--no-switch",
    )
    model = await ops_test.track_model(
        model_alias,
        model_name=model_name,
        cloud_name=k8s_cloud,
        credential_name=k8s_cloud,
        keep=False,
    )
    model_uuid = model.info.uuid
    yield model, model_alias, model_name
    timeout = 10 * 60
    with ops_test.model_context(model_alias) as model:
        keep_model = ops_test.keep_model
    await ops_test.forget_model(model_alias, timeout=timeout, allow_failure=False)

    async def model_removed():
        _, stdout, stderr = await ops_test.juju("models", "--format", "yaml")
        if _ != 0:
            return False
        model_list = yaml.safe_load(stdout)["models"]
        which = [m for m in model_list if m["model-uuid"] == model_uuid]
        return len(which) == 0

    if not keep_model:
        log.info("Removing k8s model")
        await juju.utils.block_until_with_coroutine(model_removed, timeout=timeout)
        # Update client's model cache
        await ops_test.juju("models")
        log.info("k8s model removed")
