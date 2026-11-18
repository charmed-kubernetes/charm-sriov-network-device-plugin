"""Import explicitly selected stable SR-IOV device-plugin release manifests."""

import argparse
import copy
import re
from pathlib import Path
from urllib.request import urlopen

import yaml

UPSTREAM = (
    "https://raw.githubusercontent.com/k8snetworkplumbingwg/sriov-network-device-plugin"
)
ARCHITECTURES = ("amd64", "ppc64le", "arm64")


def release_tag(value):
    """Require a stable release tag, never a moving latest or prerelease."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+", value):
        raise argparse.ArgumentTypeError("expected a stable vMAJOR.MINOR.PATCH tag")
    return value


def daemonsets_for_upgrade(resources, version):
    """Retain the charm's per-architecture identities and scheduling on upgrade."""
    result = []
    for resource in resources:
        if resource["kind"] != "DaemonSet":
            result.append(resource)
            continue
        name = resource["metadata"]["name"]
        architectures = ARCHITECTURES if name == "kube-sriov-device-plugin" else (None,)
        for architecture in architectures:
            daemonset = copy.deepcopy(resource)
            spec = daemonset["spec"]["template"]["spec"]
            if architecture:
                # Avoid leaving the old architecture-specific DaemonSets running
                # alongside a newly named upstream multi-architecture DaemonSet.
                daemonset["metadata"]["name"] = f"{name}-{architecture}"
                spec.setdefault("nodeSelector", {})["kubernetes.io/arch"] = architecture
                # Preserve the original charm's scheduling on legacy control
                # planes, without discarding any new upstream tolerations.
                tolerations = spec.get("tolerations") or []
                if not any(
                    item.get("key") == "node-role.kubernetes.io/master"
                    for item in tolerations
                ):
                    tolerations = tolerations + [
                        {
                            "key": "node-role.kubernetes.io/master",
                            "operator": "Exists",
                            "effect": "NoSchedule",
                        }
                    ]
                spec["tolerations"] = tolerations
            for container in spec["containers"]:
                image, tag = container["image"].rsplit(":", 1)
                container["image"] = f"{image}:{tag.replace('latest', version)}"
            result.append(daemonset)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("versions", nargs="+", type=release_tag)
    parser.add_argument(
        "--destination", type=Path, default=Path(__file__).parent / "manifests"
    )
    args = parser.parse_args()
    for version in args.versions:
        destination = args.destination / version
        for filename in ("configMap.yaml", "sriovdp-daemonset.yaml"):
            url = f"{UPSTREAM}/{version}/deployments/{filename}"
            with urlopen(url, timeout=60) as response:
                content = response.read().decode("utf-8")
            if filename == "sriovdp-daemonset.yaml":
                resources = daemonsets_for_upgrade(
                    list(yaml.safe_load_all(content)), version
                )
                content = yaml.safe_dump_all(resources, sort_keys=False)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / filename).write_text(
                f"# Pulled from\n# {url}\n{content}", encoding="utf-8"
            )
            print(f"Imported {version}/{filename} from {url}")


if __name__ == "__main__":
    main()
