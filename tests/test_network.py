"""Tests for Network: from_dashboard, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.network import Network


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    base = {
        "id": "N_abc",
        "organizationId": "org1",
        "name": "Corp HQ",
        "productTypes": ["switch", "appliance"],
        "timeZone": "America/Los_Angeles",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "id": "N_abc",
        "organization_id": "org1",
        "name": "Corp HQ",
        "product_types": ["switch", "appliance"],
        "time_zone": "America/Los_Angeles",
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
        n = Network.from_dashboard(_raw())
        assert n.id == "N_abc"
        assert n.organization_id == "org1"
        assert n.name == "Corp HQ"

    def test_product_types_as_list(self):
        n = Network.from_dashboard(_raw(productTypes=["switch", "wireless"]))
        assert n.product_types == ["switch", "wireless"]

    def test_tags_as_list(self):
        n = Network.from_dashboard(_raw(tags=["tag1", "tag2"]))
        assert n.tags == ["tag1", "tag2"]

    def test_time_zone_mapped(self):
        n = Network.from_dashboard(_raw(timeZone="America/New_York"))
        assert n.time_zone == "America/New_York"

    def test_optional_fields_default_none(self):
        n = Network.from_dashboard({"id": "N_1", "organizationId": "o1", "name": "X"})
        assert n.tags is None
        assert n.enrollment_string is None
        assert n.notes is None

    def test_versioning_fields_not_set(self):
        n = Network.from_dashboard(_raw())
        assert n.active_from is None
        assert n.active_to is None
        assert n.last_seen is None

    def test_unknown_keys_ignored(self):
        n = Network.from_dashboard(_raw(unknownKey="x"))
        assert n.id == "N_abc"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        n = Network.from_row(_row())
        assert n.id == "N_abc"
        assert n.organization_id == "org1"
        assert n.name == "Corp HQ"

    def test_extra_columns_ignored(self):
        n = Network.from_row({**_row(), "pg_col": "x"})
        assert n.id == "N_abc"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        n = Network.from_row({**_row(), "active_from": now, "last_seen": now})
        assert n.active_from == now
        assert n.last_seen == now

    def test_product_types_preserved(self):
        n = Network.from_row(_row(product_types=["appliance"]))
        assert n.product_types == ["appliance"]


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        n = Network(id="N_abc", organization_id="org1", name="Corp")
        assert n.resource_path == "/networks/N_abc"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Network.get("org1", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Network.get("org1", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, nets):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationNetworks.return_value = nets
        return mock_dash

    def test_returns_network_instances(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki")
        assert len(nets) == 1
        assert isinstance(nets[0], Network)

    def test_results_sorted_by_name(self):
        dash = self._make_dash([
            _raw(id="N2", name="Zulu"),
            _raw(id="N1", name="Alpha"),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki")
        assert nets[0].name == "Alpha"
        assert nets[1].name == "Zulu"

    def test_name_filter_substring_case_insensitive(self):
        dash = self._make_dash([
            _raw(id="N1", name="Corp HQ"),
            _raw(id="N2", name="Branch Office"),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki", name="corp")
        assert len(nets) == 1
        assert nets[0].id == "N1"

    def test_network_id_filter(self):
        dash = self._make_dash([_raw(id="N1"), _raw(id="N2")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki", network_id="N1")
        assert len(nets) == 1
        assert nets[0].id == "N1"

    def test_tags_include_filter(self):
        dash = self._make_dash([
            _raw(id="N1", tags=["tag1", "tag2"]),
            _raw(id="N2", tags=["other"]),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki", tags_include=["tag1"])
        assert len(nets) == 1
        assert nets[0].id == "N1"

    def test_tags_exclude_filter(self):
        dash = self._make_dash([
            _raw(id="N1", tags=["excluded"]),
            _raw(id="N2", tags=["safe"]),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki", tags_exclude=["excluded"])
        assert len(nets) == 1
        assert nets[0].id == "N2"

    def test_product_types_include_filter(self):
        dash = self._make_dash([
            _raw(id="N1", productTypes=["switch", "appliance"]),
            _raw(id="N2", productTypes=["wireless"]),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki", product_types_include=["appliance"])
        assert len(nets) == 1
        assert nets[0].id == "N1"

    def test_product_types_exclude_filter(self):
        dash = self._make_dash([
            _raw(id="N1", productTypes=["wireless"]),
            _raw(id="N2", productTypes=["switch"]),
        ])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            nets = Network.get("org1", source="meraki", product_types_exclude=["wireless"])
        assert len(nets) == 1
        assert nets[0].id == "N2"

    def test_empty_response_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert Network.get("org1", source="meraki") == []


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_org_id_always_filtered(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database")
        params = conn.execute.call_args.args[1]
        assert params["org_id"] == "org1"

    def test_name_filter_ilike(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", name="Corp")
        params = conn.execute.call_args.args[1]
        assert params["name"] == "%Corp%"

    def test_network_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", network_id="N_abc")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_tags_include_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", tags_include=["tag1"])
        params = conn.execute.call_args.args[1]
        assert params["tags_include"] == ["tag1"]
        sql = str(conn.execute.call_args.args[0])
        assert "?&" in sql

    def test_tags_exclude_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", tags_exclude=["bad"])
        params = conn.execute.call_args.args[1]
        assert params["tags_exclude"] == ["bad"]
        sql = str(conn.execute.call_args.args[0])
        assert "?|" in sql

    def test_product_types_include_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", product_types_include=["switch"])
        params = conn.execute.call_args.args[1]
        assert params["pt_include"] == ["switch"]

    def test_product_types_exclude_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", product_types_exclude=["wireless"])
        params = conn.execute.call_args.args[1]
        assert params["pt_exclude"] == ["wireless"]

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all_omits_active_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Network.get("org1", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            nets = Network.get("org1", source="database")
        assert len(nets) == 1
        assert isinstance(nets[0], Network)
