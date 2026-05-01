"""Tests for the Vlan model: from_dashboard, from_row, field mapping, data fields."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from merakisync.models.vlan import Vlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    """Minimal valid API response dict."""
    base = {
        "id": "100",
        "networkId": "N_abc123",
        "name": "Corp",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# from_dashboard
# ---------------------------------------------------------------------------

class TestFromDashboard:
    def test_id_remapped_to_vlan_id(self):
        v = Vlan.from_dashboard(_raw())
        assert v.vlan_id == 100

    def test_id_coerced_to_int(self):
        v = Vlan.from_dashboard(_raw(id="42"))
        assert isinstance(v.vlan_id, int)
        assert v.vlan_id == 42

    def test_network_id_mapped(self):
        v = Vlan.from_dashboard(_raw(networkId="N_xyz"))
        assert v.network_id == "N_xyz"

    def test_name_mapped(self):
        v = Vlan.from_dashboard(_raw(name="Management"))
        assert v.name == "Management"

    def test_appliance_ip_mapped(self):
        v = Vlan.from_dashboard(_raw(applianceIp="192.168.1.1"))
        assert v.appliance_ip == "192.168.1.1"

    def test_subnet_mapped(self):
        v = Vlan.from_dashboard(_raw(subnet="192.168.1.0/24"))
        assert v.subnet == "192.168.1.0/24"

    def test_dhcp_handling_mapped(self):
        v = Vlan.from_dashboard(_raw(dhcpHandling="Run a DHCP server"))
        assert v.dhcp_handling == "Run a DHCP server"

    def test_dhcp_boot_options_enabled_mapped(self):
        v = Vlan.from_dashboard(_raw(dhcpBootOptionsEnabled=True))
        assert v.dhcp_boot_options_enabled is True

    def test_fixed_ip_assignments_passed_through_as_dict(self):
        fipa = {"aa:bb:cc:dd:ee:ff": {"ip": "192.168.1.10", "name": "Server"}}
        v = Vlan.from_dashboard(_raw(fixedIpAssignments=fipa))
        assert v.fixed_ip_assignments == fipa

    def test_reserved_ip_ranges_passed_through_as_list(self):
        ranges = [{"start": "192.168.1.100", "end": "192.168.1.110", "comment": "Printers"}]
        v = Vlan.from_dashboard(_raw(reservedIpRanges=ranges))
        assert v.reserved_ip_ranges == ranges

    def test_mandatory_dhcp_passed_through_as_dict(self):
        v = Vlan.from_dashboard(_raw(mandatoryDhcp={"enabled": True}))
        assert v.mandatory_dhcp == {"enabled": True}

    def test_ipv6_passed_through_as_dict(self):
        ipv6 = {"enabled": False, "prefixAssignments": []}
        v = Vlan.from_dashboard(_raw(ipv6=ipv6))
        assert v.ipv6 == ipv6

    def test_unknown_keys_ignored(self):
        v = Vlan.from_dashboard(_raw(unknownField="ignored"))
        assert v.vlan_id == 100

    def test_optional_fields_default_to_none(self):
        v = Vlan.from_dashboard(_raw())
        assert v.appliance_ip is None
        assert v.subnet is None
        assert v.dhcp_handling is None
        assert v.fixed_ip_assignments is None
        assert v.ipv6 is None

    def test_versioning_fields_not_set_from_dashboard(self):
        v = Vlan.from_dashboard(_raw())
        assert v.active_from is None
        assert v.active_to is None
        assert v.last_seen is None


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_from_plain_dict(self):
        v = Vlan.from_row({
            "network_id": "N_abc",
            "vlan_id": 10,
            "name": "Guest",
            "appliance_ip": "10.0.0.1",
            "active_to": None,
        })
        assert v.network_id == "N_abc"
        assert v.vlan_id == 10
        assert v.name == "Guest"
        assert v.appliance_ip == "10.0.0.1"

    def test_extra_columns_ignored(self):
        v = Vlan.from_row({"network_id": "N_abc", "vlan_id": 1, "name": "X", "pg_col": "x"})
        assert v.vlan_id == 1

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        v = Vlan.from_row({
            "network_id": "N_abc",
            "vlan_id": 1,
            "name": "X",
            "active_from": now,
            "active_to": None,
            "last_seen": now,
        })
        assert v.active_from == now
        assert v.last_seen == now
        assert v.active_to is None


# ---------------------------------------------------------------------------
# _data_fields
# ---------------------------------------------------------------------------

class TestDataFields:
    def test_excludes_pk_fields(self):
        v = Vlan.from_dashboard(_raw())
        data = v._data_fields()
        assert "network_id" not in data
        assert "vlan_id" not in data

    def test_excludes_versioning_fields(self):
        now = datetime.now(tz=timezone.utc)
        v = Vlan(network_id="N_abc", vlan_id=1, name="X", active_from=now, last_seen=now)
        data = v._data_fields()
        assert "active_from" not in data
        assert "active_to" not in data
        assert "last_seen" not in data

    def test_includes_business_fields(self):
        v = Vlan.from_dashboard(_raw(applianceIp="10.0.0.1", subnet="10.0.0.0/24"))
        data = v._data_fields()
        assert data["name"] == "Corp"
        assert data["appliance_ip"] == "10.0.0.1"
        assert data["subnet"] == "10.0.0.0/24"
