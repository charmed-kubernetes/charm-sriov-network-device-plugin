# SR-IOV Network Device Plugin Charm

[SR-IOV Network Device Plugin][sriov-network-device-plugin] is a Kubernetes
device plugin for discovering and advertising networking resources in the form
of SR-IOV Virtual Functions (VFs) and PCI physical functions (PFs) available on
a Kubernetes host.

This charm, when deployed to a Kubernetes cloud, will create a DaemonSet that
runs the SR-IOV Network Device Plugin on every Kubernetes node in the cluster.

This charm is a component of Charmed Kubernetes. For full information,
please visit the [official Charmed Kubernetes docs](https://ubuntu.com/kubernetes/docs/cni-sriov).

[sriov-network-device-plugin]: https://github.com/k8snetworkplumbingwg/sriov-network-device-plugin

## Bundled releases

The charm bundles v3.5.1, v3.6.2, v3.7.0, v3.8.0, v3.9.0, v3.10.0 and
v3.11.0. The authoritative default is `upstream/version`, currently **v3.11.0**;
the charm does not expose a release-selection configuration option.

For CK 1.36, v3.11.0 uses the [device-plugin v1beta1 protocol][plugin-api],
which [Kubernetes 1.36 also supports][kubelet-api]. This is protocol compatibility
evidence, not upstream certification or proof of successful hardware allocation.
Before release, validate discovery, allocation, resource naming and consuming
workloads on a CK 1.36 cluster with real SR-IOV hardware, including an upgrade
from v3.5.1 with the same `resource-list` and `resource-prefix`.
The configured image registry must contain every selected image and architecture.

[plugin-api]: https://github.com/k8snetworkplumbingwg/sriov-network-device-plugin/blob/v3.11.0/pkg/resources/server.go
[kubelet-api]: https://github.com/kubernetes/kubernetes/blob/v1.36.6/staging/src/k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1/constants.go

### Updating manifests

With PyYAML installed, import only explicitly selected stable tags:

```sh
python3 upstream/update.py v3.6.2 v3.7.0 v3.8.0 v3.9.0 v3.10.0 v3.11.0
```

The updater imports `deployments/configMap.yaml` and `sriovdp-daemonset.yaml`
from each upstream tag, records their source URLs, and pins moving image tags
to that release. It leaves other bundles and the default pointer untouched.
This repository previously had no updater.

Since v3.7.0, upstream supplies one multi-architecture DaemonSet. The updater
expands it into the charm's existing amd64, arm64 and ppc64le DaemonSet names,
preserving their immutable selectors and pod labels. Stable architecture node
selectors make scheduling mutually exclusive; legacy control-plane toleration
is retained alongside upstream tolerations. This avoids orphaning the old
DaemonSets or running two device-plugin instances on each node during upgrade.
Only retain architectures actually provided by the release images. Upstream
host mounts, privileges and service-account settings remain intact; the charm
still applies its namespace, image-registry, configuration and control-plane
toleration transformations.

## Development

### Building

Build the charm with [charmcraft][]:

```
charmcraft pack
```

### Testing

Deploy Charmed Kubernetes with storage support.

Add k8s to Juju controller:

```
juju scp kubernetes-master/0:config ~/.kube/config
juju add-k8s my-k8s-cloud --controller $(juju switch | cut -d: -f1)
```

Create k8s model:

```
juju add-model my-k8s-model my-k8s-cloud
```

Deploy the SR-IOV Network Device Plugin:

```
juju deploy ./sriov-network-device-plugin.charm --resource sriov-network-device-plugin-image=nfvpe/sriov-device-plugin:v3.2
```

[charmcraft]: https://github.com/canonical/charmcraft/
