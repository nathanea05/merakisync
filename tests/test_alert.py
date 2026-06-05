"""Tests for Alert: from_dashboard (nested network flattening), from_row,
resource_path, and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.alert import Alert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    base = {
        "id": "alert1",
        "orgId": "org1",
        "type": "connectivity",
        "categoryType": "connectivity",
        "severity": "warning",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "id": "alert1",
        "org_id": "org1",
        "alert_type": "connectivity",
        "category_type": "connectivity",
        "severity": "warning",
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
    def test_basic_fields_mapped(self):
        a = Alert.from_dashboard(_raw())
        assert a.id == "alert1"
        assert a.org_id == "org1"
        assert a.alert_type == "connectivity"
        assert a.category_type == "connectivity"
        assert a.severity == "warning"

    def test_type_remapped_to_alert_type(self):
        a = Alert.from_dashboard(_raw(type="hardware"))
        assert a.alert_type == "hardware"

    def test_nested_network_flattened(self):
        a = Alert.from_dashboard(_raw(network={"id": "N_abc", "name": "Corp"}))
        assert a.network_id == "N_abc"
        assert a.network_name == "Corp"

    def test_network_key_absent_leaves_none(self):
        a = Alert.from_dashboard(_raw())
        assert a.network_id is None
        assert a.network_name is None

    def test_network_none_leaves_none(self):
        a = Alert.from_dashboard(_raw(network=None))
        assert a.network_id is None

    def test_optional_fields_default_none(self):
        a = Alert.from_dashboard({"id": "a1", "orgId": "o1"})
        assert a.started_at is None
        assert a.resolved_at is None
        assert a.dismissed_at is None
        assert a.scope is None
        assert a.title is None

    def test_scope_passed_through_as_dict(self):
        scope = {"devices": [{"serial": "Q2AB-1234"}]}
        a = Alert.from_dashboard(_raw(scope=scope))
        assert a.scope == scope

    def test_versioning_fields_not_set(self):
        a = Alert.from_dashboard(_raw())
        assert a.active_from is None
        assert a.active_to is None
        assert a.last_seen is None

    def test_unknown_keys_ignored(self):
        a = Alert.from_dashboard(_raw(extraKey="ignored"))
        assert a.id == "alert1"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        a = Alert.from_row(_row())
        assert a.id == "alert1"
        assert a.org_id == "org1"
        assert a.alert_type == "connectivity"

    def test_extra_columns_ignored(self):
        a = Alert.from_row({**_row(), "pg_internal_col": "x"})
        assert a.id == "alert1"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        a = Alert.from_row({**_row(), "active_from": now, "active_to": None, "last_seen": now})
        assert a.active_from == now
        assert a.last_seen == now
        assert a.active_to is None


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        a = Alert(id="alert1", org_id="org1")
        assert a.resource_path == "/organizations/org1/assurance/alerts/alert1"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Alert.get("org1", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Alert.get("org1", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, raw_list):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationAssuranceAlerts.return_value = raw_list
        return mock_dash

    def test_returns_alert_instances(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            alerts = Alert.get("org1", source="meraki")
        assert len(alerts) == 1
        assert isinstance(alerts[0], Alert)
        assert alerts[0].id == "alert1"

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            alerts = Alert.get("org1", source="meraki")
        assert alerts == []

    def test_active_only_passes_flag(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Alert.get("org1", source="meraki", active_only=True)
        kw = dash.organizations.getOrganizationAssuranceAlerts.call_args.kwargs
        assert kw.get("active") is True

    def test_network_id_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Alert.get("org1", source="meraki", network_id="N_abc")
        kw = dash.organizations.getOrganizationAssuranceAlerts.call_args.kwargs
        assert kw.get("networkId") == "N_abc"

    def test_severity_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Alert.get("org1", source="meraki", severity="critical")
        kw = dash.organizations.getOrganizationAssuranceAlerts.call_args.kwargs
        assert kw.get("severity") == "critical"

    def test_alert_type_passed_as_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Alert.get("org1", source="meraki", alert_type="hardware")
        kw = dash.organizations.getOrganizationAssuranceAlerts.call_args.kwargs
        assert kw.get("types") == ["hardware"]

    def test_alert_id_filtered_client_side(self):
        dash = self._make_dash([_raw(id="a1"), _raw(id="a2")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            alerts = Alert.get("org1", source="meraki", alert_id="a1")
        assert len(alerts) == 1
        assert alerts[0].id == "a1"

    def test_org_id_injected(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            alerts = Alert.get("org1", source="meraki")
        assert alerts[0].org_id == "org1"


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_ts_filter_adds_range(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts
        sql = str(conn.execute.call_args.args[0])
        assert "active_from" in sql

    def test_ts_all_omits_active_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_alert_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database", alert_id="a1")
        params = conn.execute.call_args.args[1]
        assert params["alert_id"] == "a1"

    def test_network_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database", network_id="N_abc")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_severity_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database", severity="critical")
        params = conn.execute.call_args.args[1]
        assert params["severity"] == "critical"

    def test_alert_type_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Alert.get("org1", source="database", alert_type="hardware")
        params = conn.execute.call_args.args[1]
        assert params["alert_type"] == "hardware"

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            alerts = Alert.get("org1", source="database")
        assert alerts == []

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            alerts = Alert.get("org1", source="database")
        assert len(alerts) == 1
        assert isinstance(alerts[0], Alert)
        assert alerts[0].id == "alert1"
