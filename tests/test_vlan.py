"""Tests for the Vlan model: from_dashboard, from_row, field mapping, data fields,
resource_path, and get() for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        v = Vlan(network_id="N_abc", vlan_id=100, name="Corp")
        assert v.resource_path == "/networks/N_abc/appliance/vlans/100"


# ---------------------------------------------------------------------------
# Helpers for get() tests
# ---------------------------------------------------------------------------

def _db_row(**kwargs) -> dict:
    base = {
        "network_id": "N_abc",
        "vlan_id": 100,
        "name": "Corp",
        "appliance_ip": "10.0.0.1",
        "active_to": None,
    }
    base.update(kwargs)
    return base


def _mock_engine(rows=None):
    conn = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows or []
    conn.execute.return_value = result
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = conn
    return engine, conn


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Vlan.get("N_abc", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Vlan.get("N_abc", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, vlans):
        mock_dash = MagicMock()
        mock_dash.appliance.getNetworkApplianceVlans.return_value = vlans
        return mock_dash

    def test_returns_vlan_instances(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            vlans = Vlan.get("N_abc", source="meraki")
        assert len(vlans) == 1
        assert isinstance(vlans[0], Vlan)

    def test_network_id_injected(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            vlans = Vlan.get("N_abc", source="meraki")
        assert vlans[0].network_id == "N_abc"

    def test_vlan_id_filter(self):
        dash = self._make_dash([_raw(id="100"), _raw(id="200")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            vlans = Vlan.get("N_abc", source="meraki", vlan_id=100)
        assert len(vlans) == 1
        assert vlans[0].vlan_id == 100

    def test_name_filter_substring_case_insensitive(self):
        dash = self._make_dash([_raw(id="100", name="Corp"), _raw(id="200", name="Guest")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            vlans = Vlan.get("N_abc", source="meraki", name="corp")
        assert len(vlans) == 1
        assert vlans[0].name == "Corp"

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert Vlan.get("N_abc", source="meraki") == []


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_db_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Vlan.get("N_abc", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_network_id_in_params(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Vlan.get("N_abc", source="database")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_vlan_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Vlan.get("N_abc", source="database", vlan_id=100)
        params = conn.execute.call_args.args[1]
        assert params["vlan_id"] == 100

    def test_name_filter_ilike(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Vlan.get("N_abc", source="database", name="Corp")
        params = conn.execute.call_args.args[1]
        assert params["name"] == "%Corp%"

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Vlan.get("N_abc", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Vlan.get("N_abc", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_db_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            vlans = Vlan.get("N_abc", source="database")
        assert len(vlans) == 1
        assert isinstance(vlans[0], Vlan)

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            assert Vlan.get("N_abc", source="database") == []
