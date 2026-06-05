"""Tests for Organization: from_dashboard, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.organization import Organization


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    base = {
        "id": "org1",
        "name": "Acme Corp",
        "url": "https://dashboard.meraki.com/o/org1",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "id": "org1",
        "name": "Acme Corp",
        "url": "https://dashboard.meraki.com/o/org1",
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
        o = Organization.from_dashboard(_raw())
        assert o.id == "org1"
        assert o.name == "Acme Corp"
        assert o.url == "https://dashboard.meraki.com/o/org1"

    def test_api_dict_passed_through(self):
        o = Organization.from_dashboard(_raw(api={"enabled": True}))
        assert o.api == {"enabled": True}

    def test_licensing_passed_through(self):
        o = Organization.from_dashboard(_raw(licensing={"model": "co-term"}))
        assert o.licensing == {"model": "co-term"}

    def test_optional_fields_default_none(self):
        o = Organization.from_dashboard({"id": "o1", "name": "Test", "url": "http://x"})
        assert o.api is None
        assert o.licensing is None
        assert o.cloud is None
        assert o.management is None

    def test_versioning_fields_not_set(self):
        o = Organization.from_dashboard(_raw())
        assert o.active_from is None
        assert o.active_to is None
        assert o.last_seen is None

    def test_unknown_keys_ignored(self):
        o = Organization.from_dashboard(_raw(extraKey="ignored"))
        assert o.id == "org1"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        o = Organization.from_row(_row())
        assert o.id == "org1"
        assert o.name == "Acme Corp"
        assert o.url == "https://dashboard.meraki.com/o/org1"

    def test_extra_columns_ignored(self):
        o = Organization.from_row({**_row(), "pg_internal": "x"})
        assert o.id == "org1"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        o = Organization.from_row({**_row(), "active_from": now, "last_seen": now})
        assert o.active_from == now
        assert o.last_seen == now
        assert o.active_to is None


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        o = Organization(id="org1", name="Acme", url="http://x")
        assert o.resource_path == "/organizations/org1"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Organization.get(source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Organization.get(source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, orgs):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizations.return_value = orgs
        return mock_dash

    def test_returns_organization_instances(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            orgs = Organization.get(source="meraki")
        assert len(orgs) == 1
        assert isinstance(orgs[0], Organization)

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert Organization.get(source="meraki") == []

    def test_name_filter_exact_substring(self):
        dash = self._make_dash([_raw(name="Acme Corp"), _raw(id="o2", name="Other Inc")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            orgs = Organization.get(source="meraki", name="Acme")
        assert len(orgs) == 1
        assert orgs[0].id == "org1"

    def test_name_filter_case_insensitive(self):
        dash = self._make_dash([_raw(name="Acme Corp")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            orgs = Organization.get(source="meraki", name="acme corp")
        assert len(orgs) == 1

    def test_name_filter_strips_whitespace(self):
        dash = self._make_dash([_raw(name="  Acme Corp  ")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            orgs = Organization.get(source="meraki", name="acme corp")
        assert len(orgs) == 1

    def test_name_filter_no_match_returns_empty(self):
        dash = self._make_dash([_raw(name="Acme Corp")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            orgs = Organization.get(source="meraki", name="Nonexistent")
        assert orgs == []

    def test_no_filter_returns_all(self):
        dash = self._make_dash([_raw(), _raw(id="o2", name="Other")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            orgs = Organization.get(source="meraki")
        assert len(orgs) == 2


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Organization.get(source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_name_filter_adds_ilike(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Organization.get(source="database", name="Acme")
        params = conn.execute.call_args.args[1]
        assert params["name"] == "%Acme%"
        sql = str(conn.execute.call_args.args[0])
        assert "ILIKE" in sql

    def test_ts_filter_adds_range(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Organization.get(source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts
        sql = str(conn.execute.call_args.args[0])
        assert "active_from" in sql

    def test_ts_all_omits_active_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Organization.get(source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            orgs = Organization.get(source="database")
        assert len(orgs) == 1
        assert isinstance(orgs[0], Organization)

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            assert Organization.get(source="database") == []
