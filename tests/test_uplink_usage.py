"""Tests for UplinkUsage: constructor, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.uplink_usage import UplinkUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**kwargs) -> dict:
    base = {
        "network_id": "N_abc",
        "serial": "Q2MX-1234",
        "interface": "wan1",
        "month": 6,
        "year": 2026,
        "sent": 1000,
        "received": 2000,
        "last_seen": None,
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
# Constructor / field access
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_required_fields(self):
        u = UplinkUsage(network_id="N_abc", serial="S1", interface="wan1", month=6, year=2026)
        assert u.network_id == "N_abc"
        assert u.serial == "S1"
        assert u.interface == "wan1"
        assert u.month == 6
        assert u.year == 2026

    def test_optional_bytes_default_none(self):
        u = UplinkUsage(network_id="N", serial="S", interface="wan1", month=1, year=2026)
        assert u.sent is None
        assert u.received is None

    def test_last_seen_default_none(self):
        u = UplinkUsage(network_id="N", serial="S", interface="wan1", month=1, year=2026)
        assert u.last_seen is None

    def test_not_versioned(self):
        assert UplinkUsage.__versioned__ is False


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        u = UplinkUsage.from_row(_row())
        assert u.network_id == "N_abc"
        assert u.serial == "Q2MX-1234"
        assert u.interface == "wan1"
        assert u.month == 6
        assert u.year == 2026
        assert u.sent == 1000
        assert u.received == 2000

    def test_extra_columns_ignored(self):
        u = UplinkUsage.from_row({**_row(), "pg_col": "x"})
        assert u.network_id == "N_abc"

    def test_last_seen_preserved(self):
        now = datetime.now(tz=timezone.utc)
        u = UplinkUsage.from_row({**_row(), "last_seen": now})
        assert u.last_seen == now


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        u = UplinkUsage(network_id="N_abc", serial="S1", interface="wan1", month=6, year=2026)
        assert u.resource_path == "/networks/N_abc/appliance/uplinks/usageHistory"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            UplinkUsage.get("org1", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _net_data(self, net_id, uplinks):
        return {"networkId": net_id, "byUplink": uplinks}

    def _uplink_data(self, serial, iface, sent=100, received=200):
        return {"serial": serial, "interface": iface, "sent": sent, "received": received}

    def _make_dash(self, response):
        mock_dash = MagicMock()
        mock_dash.appliance.getOrganizationApplianceUplinksUsageByNetwork.return_value = response
        return mock_dash

    def test_returns_uplink_usage_instances(self):
        response = [self._net_data("N_1", [self._uplink_data("S1", "wan1")])]
        dash = self._make_dash(response)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            usages = UplinkUsage.get("org1", source="meraki")
        assert len(usages) == 1
        assert isinstance(usages[0], UplinkUsage)

    def test_fields_mapped_correctly(self):
        now = datetime.now(tz=timezone.utc)
        response = [self._net_data("N_abc", [self._uplink_data("S1", "wan1", sent=500, received=1000)])]
        dash = self._make_dash(response)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            usages = UplinkUsage.get("org1", source="meraki")
        u = usages[0]
        assert u.network_id == "N_abc"
        assert u.serial == "S1"
        assert u.interface == "wan1"
        assert u.sent == 500
        assert u.received == 1000

    def test_month_and_year_set(self):
        response = [self._net_data("N_1", [self._uplink_data("S1", "wan1")])]
        dash = self._make_dash(response)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            usages = UplinkUsage.get("org1", source="meraki", month=3, year=2025)
        assert usages[0].month == 3
        assert usages[0].year == 2025

    def test_network_id_filter(self):
        response = [
            self._net_data("N_1", [self._uplink_data("S1", "wan1")]),
            self._net_data("N_2", [self._uplink_data("S2", "wan1")]),
        ]
        dash = self._make_dash(response)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            usages = UplinkUsage.get("org1", source="meraki", network_id="N_1")
        assert len(usages) == 1
        assert usages[0].network_id == "N_1"

    def test_serial_filter(self):
        response = [self._net_data("N_1", [
            self._uplink_data("S1", "wan1"),
            self._uplink_data("S2", "wan1"),
        ])]
        dash = self._make_dash(response)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            usages = UplinkUsage.get("org1", source="meraki", serial="S1")
        assert len(usages) == 1
        assert usages[0].serial == "S1"

    def test_interface_filter(self):
        response = [self._net_data("N_1", [
            self._uplink_data("S1", "wan1"),
            self._uplink_data("S1", "wan2"),
        ])]
        dash = self._make_dash(response)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            usages = UplinkUsage.get("org1", source="meraki", interface="wan1")
        assert len(usages) == 1
        assert usages[0].interface == "wan1"

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert UplinkUsage.get("org1", source="meraki") == []


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_month_and_year_always_in_params(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            UplinkUsage.get("org1", source="database", month=6, year=2026)
        params = conn.execute.call_args.args[1]
        assert params["month"] == 6
        assert params["year"] == 2026

    def test_defaults_to_current_month_year(self):
        engine, conn = _mock_engine([])
        now = datetime.now(tz=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            UplinkUsage.get("org1", source="database")
        params = conn.execute.call_args.args[1]
        assert params["month"] == now.month
        assert params["year"] == now.year

    def test_network_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            UplinkUsage.get("org1", source="database", network_id="N_abc")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_serial_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            UplinkUsage.get("org1", source="database", serial="S1")
        params = conn.execute.call_args.args[1]
        assert params["serial"] == "S1"

    def test_interface_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            UplinkUsage.get("org1", source="database", interface="wan1")
        params = conn.execute.call_args.args[1]
        assert params["interface"] == "wan1"

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            usages = UplinkUsage.get("org1", source="database")
        assert len(usages) == 1
        assert isinstance(usages[0], UplinkUsage)

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            assert UplinkUsage.get("org1", source="database") == []


# ---------------------------------------------------------------------------
# sync() — incremental accumulation logic
# ---------------------------------------------------------------------------

class TestSync:
    def _net_response(self, net_id, serial, iface, sent=500, received=1000):
        return {"networkId": net_id, "byUplink": [
            {"serial": serial, "interface": iface, "sent": sent, "received": received}
        ]}

    def _make_setup(self, existing_db_rows=None, api_response=None):
        """Return a context where sync() calls are mocked."""
        mock_dash = MagicMock()
        mock_dash.appliance.getOrganizationApplianceUplinksUsageByNetwork.return_value = (
            api_response or []
        )
        # Mock DB get() to return existing rows
        existing = existing_db_rows or []
        return mock_dash, existing

    def test_first_sync_sets_bytes_from_api(self):
        api_resp = [self._net_response("N1", "S1", "wan1", sent=100, received=200)]
        mock_dash, existing = self._make_setup(api_response=api_resp)
        mock_upsert = MagicMock(return_value={"upserted": 1})

        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(UplinkUsage, "get", return_value=existing) as mock_get:
                with patch.object(UplinkUsage, "upsert_many", mock_upsert):
                    result = UplinkUsage.sync("org1")

        assert len(result) == 1
        assert result[0].sent == 100
        assert result[0].received == 200

    def test_incremental_sync_accumulates_bytes(self):
        now_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        existing = [UplinkUsage(
            network_id="N1", serial="S1", interface="wan1",
            month=6, year=2026, sent=1000, received=2000, last_seen=now_ts
        )]
        api_resp = [self._net_response("N1", "S1", "wan1", sent=100, received=200)]
        mock_dash = MagicMock()
        mock_dash.appliance.getOrganizationApplianceUplinksUsageByNetwork.return_value = api_resp
        mock_upsert = MagicMock(return_value={"upserted": 1})

        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(UplinkUsage, "get", return_value=existing) as mock_get:
                with patch.object(UplinkUsage, "upsert_many", mock_upsert):
                    result = UplinkUsage.sync("org1")

        assert result[0].sent == 1100   # 1000 + 100
        assert result[0].received == 2200  # 2000 + 200

    def test_empty_api_response_returns_empty_list(self):
        mock_dash = MagicMock()
        mock_dash.appliance.getOrganizationApplianceUplinksUsageByNetwork.return_value = []

        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(UplinkUsage, "get", return_value=[]):
                result = UplinkUsage.sync("org1")

        assert result == []

    def test_gap_warning_logged_when_stale(self):
        from datetime import timedelta
        old_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)  # well over 30 days ago
        existing = [UplinkUsage(
            network_id="N1", serial="S1", interface="wan1",
            month=1, year=2026, sent=0, received=0, last_seen=old_ts
        )]
        mock_dash = MagicMock()
        mock_dash.appliance.getOrganizationApplianceUplinksUsageByNetwork.return_value = []

        import logging
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(UplinkUsage, "get", return_value=existing):
                with patch("merakisync.models.uplink_usage.logger") as mock_logger:
                    UplinkUsage.sync("org1")
        # Warning should have been logged for the gap
        mock_logger.warning.assert_called()

    def test_last_seen_set_to_t1(self):
        api_resp = [self._net_response("N1", "S1", "wan1")]
        mock_dash = MagicMock()
        mock_dash.appliance.getOrganizationApplianceUplinksUsageByNetwork.return_value = api_resp
        captured = []

        def capture_upsert(rows, **kw):
            captured.extend(rows)
            return {"upserted": len(rows)}

        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(UplinkUsage, "get", return_value=[]):
                with patch.object(UplinkUsage, "upsert_many", side_effect=capture_upsert):
                    UplinkUsage.sync("org1")

        assert captured[0].last_seen is not None
