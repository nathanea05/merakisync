"""Tests for Uplink: from_dashboard, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.uplink import Uplink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    """Raw uplink dict as it would appear after flattening from the API."""
    base = {
        "serial": "Q2MX-1234-5678",
        "networkId": "N_abc",
        "interface": "wan1",
        "status": "active",
        "ip": "1.2.3.4",
        "gateway": "1.2.3.1",
        "publicIp": "5.6.7.8",
        "ipAssignedBy": "static",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "serial": "Q2MX-1234-5678",
        "network_id": "N_abc",
        "interface": "wan1",
        "status": "active",
        "ip": "1.2.3.4",
        "gateway": "1.2.3.1",
        "public_ip": "5.6.7.8",
        "ip_assigned_by": "static",
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


# API response wrapper (nested structure)
def _api_device(serial, net_id, uplinks):
    return {"serial": serial, "networkId": net_id, "uplinks": uplinks}


# ---------------------------------------------------------------------------
# from_dashboard
# ---------------------------------------------------------------------------

class TestFromDashboard:
    def test_serial_mapped(self):
        u = Uplink.from_dashboard(_raw())
        assert u.serial == "Q2MX-1234-5678"

    def test_interface_mapped(self):
        u = Uplink.from_dashboard(_raw(interface="wan2"))
        assert u.interface == "wan2"

    def test_network_id_mapped(self):
        u = Uplink.from_dashboard(_raw())
        assert u.network_id == "N_abc"

    def test_status_mapped(self):
        u = Uplink.from_dashboard(_raw(status="failed"))
        assert u.status == "failed"

    def test_ip_fields_mapped(self):
        u = Uplink.from_dashboard(_raw())
        assert u.ip == "1.2.3.4"
        assert u.gateway == "1.2.3.1"
        assert u.public_ip == "5.6.7.8"

    def test_ip_assigned_by_mapped(self):
        u = Uplink.from_dashboard(_raw(ipAssignedBy="dhcp"))
        assert u.ip_assigned_by == "dhcp"

    def test_cellular_fields_optional(self):
        u = Uplink.from_dashboard(_raw(apn="internet", signalType="4G"))
        assert u.apn == "internet"
        assert u.signal_type == "4G"

    def test_optional_fields_default_none(self):
        u = Uplink.from_dashboard({"serial": "S1", "interface": "wan1"})
        assert u.ip is None
        assert u.gateway is None
        assert u.signal_stat is None
        assert u.iccid is None
        assert u.provider is None

    def test_versioning_fields_not_set(self):
        u = Uplink.from_dashboard(_raw())
        assert u.active_from is None
        assert u.active_to is None
        assert u.last_seen is None

    def test_unknown_keys_ignored(self):
        u = Uplink.from_dashboard(_raw(extraKey="x"))
        assert u.serial == "Q2MX-1234-5678"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        u = Uplink.from_row(_row())
        assert u.serial == "Q2MX-1234-5678"
        assert u.interface == "wan1"
        assert u.ip_assigned_by == "static"

    def test_extra_columns_ignored(self):
        u = Uplink.from_row({**_row(), "pg_col": "x"})
        assert u.serial == "Q2MX-1234-5678"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        u = Uplink.from_row({**_row(), "active_from": now, "active_to": None, "last_seen": now})
        assert u.active_from == now
        assert u.last_seen == now
        assert u.active_to is None


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        u = Uplink(serial="Q2MX-1234", interface="wan1")
        assert u.resource_path == "/devices/Q2MX-1234"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Uplink.get("org1", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Uplink.get("org1", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, response):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationUplinksStatuses.return_value = response
        return mock_dash

    def test_returns_uplink_instances(self):
        raw_uplink = {"interface": "wan1", "status": "active", "ip": "1.2.3.4"}
        dash = self._make_dash([_api_device("S1", "N_1", [raw_uplink])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            uplinks = Uplink.get("org1", source="meraki")
        assert len(uplinks) == 1
        assert isinstance(uplinks[0], Uplink)

    def test_serial_injected_from_device(self):
        raw_uplink = {"interface": "wan1"}
        dash = self._make_dash([_api_device("S1", "N_1", [raw_uplink])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            uplinks = Uplink.get("org1", source="meraki")
        assert uplinks[0].serial == "S1"

    def test_network_id_injected(self):
        raw_uplink = {"interface": "wan1"}
        dash = self._make_dash([_api_device("S1", "N_abc", [raw_uplink])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            uplinks = Uplink.get("org1", source="meraki")
        assert uplinks[0].network_id == "N_abc"

    def test_network_id_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Uplink.get("org1", source="meraki", network_id="N_abc")
        kw = dash.organizations.getOrganizationUplinksStatuses.call_args.kwargs
        assert kw.get("networkIds") == ["N_abc"]

    def test_serial_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Uplink.get("org1", source="meraki", serial="S1")
        kw = dash.organizations.getOrganizationUplinksStatuses.call_args.kwargs
        assert kw.get("serials") == ["S1"]

    def test_interface_filtered_client_side(self):
        raw_wan1 = {"interface": "wan1", "status": "active"}
        raw_wan2 = {"interface": "wan2", "status": "active"}
        dash = self._make_dash([_api_device("S1", "N_1", [raw_wan1, raw_wan2])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            uplinks = Uplink.get("org1", source="meraki", interface="wan1")
        assert len(uplinks) == 1
        assert uplinks[0].interface == "wan1"

    def test_status_filtered_client_side(self):
        raw_active = {"interface": "wan1", "status": "active"}
        raw_failed = {"interface": "wan2", "status": "failed"}
        dash = self._make_dash([_api_device("S1", "N_1", [raw_active, raw_failed])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            uplinks = Uplink.get("org1", source="meraki", status="active")
        assert len(uplinks) == 1
        assert uplinks[0].status == "active"

    def test_ip_assigned_by_filter(self):
        raw_static = {"interface": "wan1", "ipAssignedBy": "static"}
        raw_dhcp = {"interface": "wan2", "ipAssignedBy": "dhcp"}
        dash = self._make_dash([_api_device("S1", "N_1", [raw_static, raw_dhcp])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            uplinks = Uplink.get("org1", source="meraki", ip_assigned_by="static")
        assert len(uplinks) == 1
        assert uplinks[0].ip_assigned_by == "static"

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert Uplink.get("org1", source="meraki") == []


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_serial_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", serial="S1")
        params = conn.execute.call_args.args[1]
        assert params["serial"] == "S1"

    def test_network_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", network_id="N_abc")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_interface_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", interface="wan1")
        params = conn.execute.call_args.args[1]
        assert params["interface"] == "wan1"

    def test_status_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", status="active")
        params = conn.execute.call_args.args[1]
        assert params["status"] == "active"

    def test_ip_assigned_by_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", ip_assigned_by="static")
        params = conn.execute.call_args.args[1]
        assert params["ip_assigned_by"] == "static"

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Uplink.get("org1", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            uplinks = Uplink.get("org1", source="database")
        assert len(uplinks) == 1
        assert isinstance(uplinks[0], Uplink)

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            assert Uplink.get("org1", source="database") == []
