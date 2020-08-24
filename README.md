# SR-IOV Network Device Plugin Charm

This is an early proof-of-concept for deploying and managing Intel's
[SR-IOV Network Device Plugin](https://github.com/intel/sriov-network-device-plugin/)
via Juju.

## Development

### Building
Build the charm:

```
make charm
```

### Uploading
To upload to the charm store:

```
make upload NAMESPACE=<NAMESPACE> CHANNEL=<CHANNEL>
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
juju deploy cs:~${NAMESPACE}/sriov-network-device-plugin --channel edge
```
