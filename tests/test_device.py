"""Tests for Device: from_dashboard, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.device import Device


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    base = {
        "serial": "Q2AB-1234-5678",
        "name": "Core Switch",
        "networkId": "N_abc",
        "model": "MS220-8P",
        "mac": "aa:bb:cc:dd:ee:ff",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "serial": "Q2AB-1234-5678",
        "name": "Core Switch",
        "network_id": "N_abc",
        "model": "MS220-8P",
        "mac": "aa:bb:cc:dd:ee:ff",
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
# from_dashboard
# ---------------------------------------------------------------------------

class TestFromDashboard:
    def test_basic_fields(self):
        d = Device.from_dashboard(_raw())
        assert d.serial == "Q2AB-1234-5678"
        assert d.name == "Core Switch"
        assert d.network_id == "N_abc"
        assert d.model == "MS220-8P"

    def test_tags_as_list(self):
        d = Device.from_dashboard(_raw(tags=["tag1", "tag2"]))
        assert d.tags == ["tag1", "tag2"]

    def test_lat_lng_mapped(self):
        d = Device.from_dashboard(_raw(lat=37.77, lng=-122.42))
        assert d.lat == 37.77
        assert d.lng == -122.42

    def test_optional_fields_default_none(self):
        d = Device.from_dashboard({"serial": "Q2AB-1234-5678"})
        assert d.name is None
        assert d.network_id is None
        assert d.model is None
        assert d.firmware is None
        assert d.floor_plan_id is None

    def test_versioning_fields_not_set(self):
        d = Device.from_dashboard(_raw())
        assert d.active_from is None
        assert d.active_to is None
        assert d.last_seen is None

    def test_unknown_keys_ignored(self):
        d = Device.from_dashboard(_raw(unknownField="x"))
        assert d.serial == "Q2AB-1234-5678"

    def test_details_passed_through_as_list(self):
        details = [{"name": "wan1 ip", "value": "1.2.3.4"}]
        d = Device.from_dashboard(_raw(details=details))
        assert d.details == details

    def test_beacon_id_params_as_dict(self):
        bip = {"uuid": "abc-123", "major": 0, "minor": 1}
        d = Device.from_dashboard(_raw(beaconIdParams=bip))
        assert d.beacon_id_params == bip


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        d = Device.from_row(_row())
        assert d.serial == "Q2AB-1234-5678"
        assert d.name == "Core Switch"
        assert d.network_id == "N_abc"

    def test_extra_columns_ignored(self):
        d = Device.from_row({**_row(), "pg_col": "x"})
        assert d.serial == "Q2AB-1234-5678"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        d = Device.from_row({**_row(), "active_from": now, "active_to": None, "last_seen": now})
        assert d.active_from == now
        assert d.last_seen == now
        assert d.active_to is None


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        d = Device(serial="Q2AB-1234-5678")
        assert d.resource_path == "/devices/Q2AB-1234-5678"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Device.get("org1", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Device.get("org1", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, devs):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationDevices.return_value = devs
        return mock_dash

    def test_returns_device_instances(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            devs = Device.get("org1", source="meraki")
        assert len(devs) == 1
        assert isinstance(devs[0], Device)

    def test_serial_passed_to_api(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Device.get("org1", source="meraki", serial="Q2AB-1234-5678")
        kw = dash.organizations.getOrganizationDevices.call_args.kwargs
        assert kw.get("serial") == "Q2AB-1234-5678"

    def test_network_id_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Device.get("org1", source="meraki", network_id="N_abc")
        kw = dash.organizations.getOrganizationDevices.call_args.kwargs
        assert kw.get("networkIds") == ["N_abc"]

    def test_product_types_include_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Device.get("org1", source="meraki", product_types_include=["switch"])
        kw = dash.organizations.getOrganizationDevices.call_args.kwargs
        assert kw.get("productTypes") == ["switch"]

    def test_model_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Device.get("org1", source="meraki", model="MS220")
        kw = dash.organizations.getOrganizationDevices.call_args.kwargs
        assert kw.get("model") == "MS220"

    def test_name_filtered_client_side(self):
        # name is NOT passed to API — applied client-side after response
        dash = self._make_dash([
            _raw(serial="S1", name="Core Switch"),
            _raw(serial="S2", name="Edge Router"),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            devs = Device.get("org1", source="meraki", name="core")
        kw = dash.organizations.getOrganizationDevices.call_args.kwargs
        assert "name" not in kw  # not passed to API
        assert len(devs) == 1
        assert devs[0].serial == "S1"

    def test_name_filter_case_insensitive(self):
        dash = self._make_dash([_raw(name="CORE Switch")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            devs = Device.get("org1", source="meraki", name="core switch")
        assert len(devs) == 1

    def test_status_filter_client_side(self):
        dash = self._make_dash([
            _raw(serial="S1", status="online"),
            _raw(serial="S2", status="offline"),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            devs = Device.get("org1", source="meraki", status="online")
        assert len(devs) == 1
        assert devs[0].serial == "S1"

    def test_product_types_exclude_client_side(self):
        # appliance → MX, switch → MS, wireless → MR
        dash = self._make_dash([
            _raw(serial="S1", model="MS220-8P"),   # switch
            _raw(serial="S2", model="MX67"),        # appliance
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            devs = Device.get("org1", source="meraki", product_types_exclude=["appliance"])
        assert len(devs) == 1
        assert devs[0].serial == "S1"

    def test_tags_exclude_filter(self):
        dash = self._make_dash([
            _raw(serial="S1", tags=["excluded"]),
            _raw(serial="S2", tags=["safe"]),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            devs = Device.get("org1", source="meraki", tags_exclude=["excluded"])
        assert len(devs) == 1
        assert devs[0].serial == "S2"

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert Device.get("org1", source="meraki") == []


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_serial_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", serial="Q2AB-1234-5678")
        params = conn.execute.call_args.args[1]
        assert params["serial"] == "Q2AB-1234-5678"

    def test_name_filter_ilike(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", name="core")
        params = conn.execute.call_args.args[1]
        assert params["name"] == "%core%"

    def test_network_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", network_id="N_abc")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_model_filter_ilike(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", model="MS220")
        params = conn.execute.call_args.args[1]
        assert params["model"] == "%MS220%"

    def test_status_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", status="online")
        params = conn.execute.call_args.args[1]
        assert params["status"] == "online"

    def test_tags_include_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", tags_include=["tag1"])
        params = conn.execute.call_args.args[1]
        assert params["tags_include"] == ["tag1"]

    def test_tags_exclude_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", tags_exclude=["bad"])
        params = conn.execute.call_args.args[1]
        assert params["tags_exclude"] == ["bad"]

    def test_product_types_include_adds_model_prefix(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", product_types_include=["switch"])
        params = conn.execute.call_args.args[1]
        assert params["incl_prefix_0"] == "MS%"

    def test_product_types_exclude_adds_not_ilike(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", product_types_exclude=["appliance"])
        params = conn.execute.call_args.args[1]
        assert params["excl_prefix_0"] == "MX%"

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all_omits_active_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Device.get("org1", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            devs = Device.get("org1", source="database")
        assert len(devs) == 1
        assert isinstance(devs[0], Device)

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            assert Device.get("org1", source="database") == []
