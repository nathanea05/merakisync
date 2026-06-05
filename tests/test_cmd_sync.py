"""Tests for cmd_sync.run(): SyncFlags orchestration logic."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from merakisync.cli.cmd_sync import SyncFlags, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _org(org_id="org1", name="Acme"):
    org = MagicMock()
    org.id = org_id
    org.name = name
    return org


def _net(net_id, product_types=None):
    net = MagicMock()
    net.id = net_id
    net.name = f"Net-{net_id}"
    net.product_types = product_types or []
    return net


def _mock_models(orgs=None, networks=None):
    """Patch all model classes used by run() and return mocks dict."""
    mocks = {}
    patches = {
        "Organization": "merakisync.models.organization.Organization",
        "Network":       "merakisync.models.network.Network",
        "Device":        "merakisync.models.device.Device",
        "Switchport":    "merakisync.models.switchport.Switchport",
        "Uplink":        "merakisync.models.uplink.Uplink",
        "UplinkUsage":   "merakisync.models.uplink_usage.UplinkUsage",
        "DhcpServerPolicy": "merakisync.models.dhcp_server_policy.DhcpServerPolicy",
        "Alert":         "merakisync.models.alert.Alert",
        "L3FirewallRule": "merakisync.models.l3_firewall_rule.L3FirewallRule",
        "Vlan":          "merakisync.models.vlan.Vlan",
        "Ssid":          "merakisync.models.ssid.Ssid",
    }
    active_patches = []
    for name, target in patches.items():
        p = patch(target)
        mock = p.start()
        mocks[name] = mock
        active_patches.append(p)

    orgs = orgs if orgs is not None else [_org()]
    networks = networks if networks is not None else []

    mocks["Organization"].sync.return_value = orgs
    mocks["Organization"].get.return_value = orgs
    mocks["Network"].sync.return_value = networks
    mocks["Network"].get.return_value = networks
    mocks["Device"].sync.return_value = []
    mocks["Switchport"].sync.return_value = []
    mocks["Uplink"].sync.return_value = []
    mocks["UplinkUsage"].sync.return_value = []
    mocks["Alert"].sync.return_value = []
    mocks["DhcpServerPolicy"].sync.return_value = []
    mocks["L3FirewallRule"].sync.return_value = []
    mocks["Vlan"].sync.return_value = []
    mocks["Ssid"].sync.return_value = []

    return mocks, active_patches


# ---------------------------------------------------------------------------
# SyncFlags
# ---------------------------------------------------------------------------

class TestSyncFlagsProperty:
    def test_all_false_is_sync_all(self):
        assert SyncFlags().sync_all is True

    def test_single_flag_not_sync_all(self):
        assert SyncFlags(organizations=True).sync_all is False

    def test_default_none_gives_sync_all(self):
        flags = SyncFlags()
        assert flags.sync_all is True


# ---------------------------------------------------------------------------
# run() — no orgs aborts
# ---------------------------------------------------------------------------

class TestRunNoOrgs:
    def test_no_orgs_returns_early(self):
        mocks, patches = _mock_models(orgs=[])
        try:
            run()
            mocks["Network"].sync.assert_not_called()
        finally:
            for p in patches:
                p.stop()


# ---------------------------------------------------------------------------
# run() — selective flags
# ---------------------------------------------------------------------------

class TestRunSelectiveFlags:
    def setup_method(self):
        self.mocks, self.patches = _mock_models()

    def teardown_method(self):
        for p in self.patches:
            p.stop()

    def test_organizations_flag_syncs_orgs(self):
        run(SyncFlags(organizations=True))
        self.mocks["Organization"].sync.assert_called_once()

    def test_no_org_flag_fetches_without_sync(self):
        run(SyncFlags(devices=True))
        self.mocks["Organization"].sync.assert_not_called()
        self.mocks["Organization"].get.assert_called_once()

    def test_alerts_flag_calls_alert_sync(self):
        run(SyncFlags(alerts=True))
        self.mocks["Alert"].sync.assert_called_once_with("org1")

    def test_uplinks_flag_calls_uplink_sync(self):
        run(SyncFlags(uplinks=True))
        self.mocks["Uplink"].sync.assert_called_once_with("org1")

    def test_uplink_usage_flag_calls_uplink_usage_sync(self):
        run(SyncFlags(uplink_usage=True))
        self.mocks["UplinkUsage"].sync.assert_called_once_with("org1")

    def test_devices_flag_calls_device_sync(self):
        run(SyncFlags(devices=True))
        self.mocks["Device"].sync.assert_called_once_with("org1")

    def test_switchports_flag_calls_switchport_sync(self):
        run(SyncFlags(switchports=True))
        self.mocks["Switchport"].sync.assert_called_once_with("org1")

    def test_no_network_dependent_flags_skips_network_fetch(self):
        run(SyncFlags(devices=True))
        # No vlans/ssids/dhcp/firewall flags → network loop skipped
        self.mocks["Network"].sync.assert_not_called()
        self.mocks["Network"].get.assert_not_called()


# ---------------------------------------------------------------------------
# run() — per-network resources
# ---------------------------------------------------------------------------

class TestRunPerNetworkResources:
    def setup_method(self):
        self.mocks, self.patches = _mock_models(
            networks=[
                _net("N1", product_types=["switch", "appliance", "wireless"]),
            ]
        )

    def teardown_method(self):
        for p in self.patches:
            p.stop()

    def test_networks_flag_syncs_networks(self):
        run(SyncFlags(networks=True))
        self.mocks["Network"].sync.assert_called_once_with("org1")

    def test_vlans_flag_requires_appliance_network(self):
        run(SyncFlags(vlans=True))
        self.mocks["Vlan"].sync.assert_called_once_with("N1")

    def test_ssids_flag_requires_wireless_network(self):
        run(SyncFlags(ssids=True))
        self.mocks["Ssid"].sync.assert_called_once_with("N1")

    def test_dhcp_flag_requires_switch_network(self):
        run(SyncFlags(dhcp_server_policy=True))
        self.mocks["DhcpServerPolicy"].sync.assert_called_once_with("N1")

    def test_l3_firewall_flag_requires_appliance_network(self):
        run(SyncFlags(l3_firewall_rules=True))
        self.mocks["L3FirewallRule"].sync.assert_called_once_with("N1")

    def test_non_appliance_network_skips_vlans(self):
        # Override with a wireless-only network
        self.mocks["Network"].sync.return_value = [_net("N2", product_types=["wireless"])]
        self.mocks["Network"].get.return_value = [_net("N2", product_types=["wireless"])]
        run(SyncFlags(vlans=True))
        self.mocks["Vlan"].sync.assert_not_called()


# ---------------------------------------------------------------------------
# run() — sync_all (no flags)
# ---------------------------------------------------------------------------

class TestRunSyncAll:
    def setup_method(self):
        self.mocks, self.patches = _mock_models(
            networks=[_net("N1", product_types=["switch", "appliance"])]
        )

    def teardown_method(self):
        for p in self.patches:
            p.stop()

    def test_sync_all_syncs_orgs(self):
        run()
        self.mocks["Organization"].sync.assert_called_once()

    def test_sync_all_syncs_networks(self):
        run()
        self.mocks["Network"].sync.assert_called_once_with("org1")

    def test_sync_all_syncs_devices(self):
        run()
        self.mocks["Device"].sync.assert_called_once_with("org1")

    def test_sync_all_syncs_alerts(self):
        run()
        self.mocks["Alert"].sync.assert_called_once_with("org1")

    def test_sync_all_flags_none_same_as_empty_flags(self):
        run(None)
        self.mocks["Organization"].sync.assert_called_once()
