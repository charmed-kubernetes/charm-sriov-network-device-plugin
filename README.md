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
