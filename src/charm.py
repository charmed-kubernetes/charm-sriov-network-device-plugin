#!/usr/bin/env python3

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.manifests import Collector
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from manifests import SRIOVNetworkDevicePluginManifests

log = logging.getLogger()


class SRIOVNetworkDevicePluginCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.manifests = SRIOVNetworkDevicePluginManifests(self, self.config)
        self.collector = Collector(self.manifests)
        self.framework.observe(self.on.config_changed, self.config_changed)
        self.framework.observe(self.on.update_status, self.update_status)

    def config_changed(self, event):
        if not self.manifests.error:
            self.manifests.apply_manifests()

        self.update_status(event)

    def update_status(self, event):
        error = self.manifests.error
        if error:
            self.model.unit.status = BlockedStatus(error)
            return

        unready = self.collector.unready
        if unready:
            self.unit.status = WaitingStatus(", ".join(unready))
        else:
            self.unit.status = ActiveStatus()
            self.unit.set_workload_version(self.collector.short_version)
            if self.unit.is_leader():
                self.app.status = ActiveStatus(self.collector.long_version)


if __name__ == "__main__":
    main(SRIOVNetworkDevicePluginCharm)  # pragma: no cover
