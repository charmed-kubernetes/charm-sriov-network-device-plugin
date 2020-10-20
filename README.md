# SR-IOV Network Device Plugin Charm

This is an early proof-of-concept for deploying and managing Intel's
[SR-IOV Network Device Plugin](https://github.com/intel/sriov-network-device-plugin/)
via Juju.

## Development

### Building

Build the charm with [charmcraft][]:

```
charmcraft build
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
