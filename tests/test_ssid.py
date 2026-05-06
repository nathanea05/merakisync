"""Tests for the Ssid model: from_dashboard, from_row, field mapping, data fields."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from merakisync.models.ssid import Ssid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    """Minimal valid API response dict (network_id injected by sync)."""
    base = {
        "networkId": "N_abc123",
        "number": 0,
        "name": "Corp-WiFi",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    """Minimal valid DB row dict."""
    base = {
        "network_id": "N_abc123",
        "number": 0,
        "name": "Corp-WiFi",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# from_dashboard
# ---------------------------------------------------------------------------

class TestFromDashboard:
    def test_network_id_mapped(self):
        s = Ssid.from_dashboard(_raw(networkId="N_xyz"))
        assert s.network_id == "N_xyz"

    def test_number_mapped(self):
        s = Ssid.from_dashboard(_raw(number=5))
        assert s.number == 5

    def test_name_mapped(self):
        s = Ssid.from_dashboard(_raw(name="Guest"))
        assert s.name == "Guest"

    def test_enabled_mapped(self):
        s = Ssid.from_dashboard(_raw(enabled=True))
        assert s.enabled is True

    def test_auth_mode_camel_to_snake(self):
        s = Ssid.from_dashboard(_raw(authMode="psk"))
        assert s.auth_mode == "psk"

    def test_encryption_mode_mapped(self):
        s = Ssid.from_dashboard(_raw(encryptionMode="wpa"))
        assert s.encryption_mode == "wpa"

    def test_wpa_encryption_mode_mapped(self):
        s = Ssid.from_dashboard(_raw(wpaEncryptionMode="WPA2 only"))
        assert s.wpa_encryption_mode == "WPA2 only"

    def test_splash_page_mapped(self):
        s = Ssid.from_dashboard(_raw(splashPage="None"))
        assert s.splash_page == "None"

    def test_ssid_admin_accessible_mapped(self):
        s = Ssid.from_dashboard(_raw(ssidAdminAccessible=False))
        assert s.ssid_admin_accessible is False

    def test_radius_servers_mapped(self):
        servers = [{"host": "1.2.3.4", "port": 1812}]
        s = Ssid.from_dashboard(_raw(radiusServers=servers))
        assert s.radius_servers == servers

    def test_radius_accounting_servers_mapped(self):
        servers = [{"host": "1.2.3.4", "port": 1813}]
        s = Ssid.from_dashboard(_raw(radiusAccountingServers=servers))
        assert s.radius_accounting_servers == servers

    def test_radius_enabled_mapped(self):
        s = Ssid.from_dashboard(_raw(radiusEnabled=True))
        assert s.radius_enabled is True

    def test_radius_accounting_enabled_mapped(self):
        s = Ssid.from_dashboard(_raw(radiusAccountingEnabled=False))
        assert s.radius_accounting_enabled is False

    def test_radius_attribute_for_group_policies_mapped(self):
        s = Ssid.from_dashboard(_raw(radiusAttributeForGroupPolicies="Filter-Id"))
        assert s.radius_attribute_for_group_policies == "Filter-Id"

    def test_radius_failover_policy_mapped(self):
        s = Ssid.from_dashboard(_raw(radiusFailoverPolicy="Deny access"))
        assert s.radius_failover_policy == "Deny access"

    def test_radius_load_balancing_policy_mapped(self):
        s = Ssid.from_dashboard(_raw(radiusLoadBalancingPolicy="Round robin"))
        assert s.radius_load_balancing_policy == "Round robin"

    def test_ip_assignment_mode_mapped(self):
        s = Ssid.from_dashboard(_raw(ipAssignmentMode="NAT mode"))
        assert s.ip_assignment_mode == "NAT mode"

    def test_walled_garden_enabled_mapped(self):
        s = Ssid.from_dashboard(_raw(walledGardenEnabled=True))
        assert s.walled_garden_enabled is True

    def test_walled_garden_ranges_mapped(self):
        ranges = ["192.168.0.0/24", "example.com"]
        s = Ssid.from_dashboard(_raw(walledGardenRanges=ranges))
        assert s.walled_garden_ranges == ranges

    def test_band_selection_mapped(self):
        s = Ssid.from_dashboard(_raw(bandSelection="5 GHz band only"))
        assert s.band_selection == "5 GHz band only"

    def test_per_client_bandwidth_limits_mapped(self):
        s = Ssid.from_dashboard(_raw(perClientBandwidthLimitUp=1000, perClientBandwidthLimitDown=5000))
        assert s.per_client_bandwidth_limit_up == 1000
        assert s.per_client_bandwidth_limit_down == 5000

    def test_per_ssid_bandwidth_limits_mapped(self):
        s = Ssid.from_dashboard(_raw(perSsidBandwidthLimitUp=0, perSsidBandwidthLimitDown=0))
        assert s.per_ssid_bandwidth_limit_up == 0
        assert s.per_ssid_bandwidth_limit_down == 0

    def test_availability_tags_mapped(self):
        s = Ssid.from_dashboard(_raw(availabilityTags=["floor-1", "floor-2"]))
        assert s.availability_tags == ["floor-1", "floor-2"]

    def test_available_on_all_aps_mapped(self):
        s = Ssid.from_dashboard(_raw(availableOnAllAps=False))
        assert s.available_on_all_aps is False

    def test_mandatory_dhcp_enabled_mapped(self):
        s = Ssid.from_dashboard(_raw(mandatoryDhcpEnabled=True))
        assert s.mandatory_dhcp_enabled is True

    def test_unknown_fields_ignored(self):
        s = Ssid.from_dashboard(_raw(unknownFutureField="ignored"))
        assert s.name == "Corp-WiFi"

    def test_missing_optional_fields_default_none(self):
        s = Ssid.from_dashboard({"networkId": "N_abc", "number": 0, "name": "X"})
        assert s.auth_mode is None
        assert s.radius_servers is None
        assert s.enabled is None


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_basic_row(self):
        s = Ssid.from_row(_row())
        assert s.network_id == "N_abc123"
        assert s.number == 0
        assert s.name == "Corp-WiFi"

    def test_optional_fields_from_row(self):
        s = Ssid.from_row(_row(auth_mode="open", enabled=True, min_bitrate=11))
        assert s.auth_mode == "open"
        assert s.enabled is True
        assert s.min_bitrate == 11

    def test_versioning_fields_from_row(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        s = Ssid.from_row(_row(active_from=ts, active_to=None, last_seen=ts))
        assert s.active_from == ts
        assert s.active_to is None
        assert s.last_seen == ts

    def test_extra_db_columns_ignored(self):
        s = Ssid.from_row(_row(nonexistent_column="ignored"))
        assert s.network_id == "N_abc123"

    def test_list_fields_round_trip(self):
        import json
        servers = [{"host": "1.2.3.4", "port": 1812}]
        s = Ssid.from_row(_row(radius_servers=json.dumps(servers)))
        # from_row stores the raw DB value; JSON parsing is the caller's responsibility
        assert s.radius_servers == json.dumps(servers)


# ---------------------------------------------------------------------------
# _data_fields
# ---------------------------------------------------------------------------

class TestDataFields:
    def test_excludes_pk(self):
        s = Ssid.from_row(_row())
        data = s._data_fields()
        assert "network_id" not in data
        assert "number" not in data

    def test_excludes_versioning_fields(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        s = Ssid.from_row(_row(active_from=ts, active_to=None, last_seen=ts))
        data = s._data_fields()
        assert "active_from" not in data
        assert "active_to" not in data
        assert "last_seen" not in data

    def test_includes_business_fields(self):
        s = Ssid.from_row(_row(name="Test", auth_mode="psk", enabled=True))
        data = s._data_fields()
        assert data["name"] == "Test"
        assert data["auth_mode"] == "psk"
        assert data["enabled"] is True
