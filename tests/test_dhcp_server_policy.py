"""Tests for DhcpServerPolicy: from_dashboard, from_row, resource_path,
and get() for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.dhcp_server_policy import DhcpServerPolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    base = {
        "networkId": "N_abc",
        "defaultPolicy": "block",
        "blockedServers": ["10.0.0.5"],
        "allowedServers": ["10.0.0.1"],
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "network_id": "N_abc",
        "default_policy": "block",
        "blocked_servers": ["10.0.0.5"],
        "allowed_servers": ["10.0.0.1"],
        "active_to": None,
    }
    base.update(kwargs)
    return base


def _mock_engine(rows=None, fetchone=None):
    conn = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows or []
    result.mappings.return_value.fetchone.return_value = fetchone
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
    def test_network_id_from_networkId(self):
        p = DhcpServerPolicy.from_dashboard(_raw())
        assert p.network_id == "N_abc"

    def test_default_policy_mapped(self):
        p = DhcpServerPolicy.from_dashboard(_raw(defaultPolicy="allow"))
        assert p.default_policy == "allow"

    def test_blocked_servers_as_list(self):
        p = DhcpServerPolicy.from_dashboard(_raw(blockedServers=["10.0.0.5", "10.0.0.6"]))
        assert p.blocked_servers == ["10.0.0.5", "10.0.0.6"]

    def test_allowed_servers_as_list(self):
        p = DhcpServerPolicy.from_dashboard(_raw(allowedServers=["10.0.0.1"]))
        assert p.allowed_servers == ["10.0.0.1"]

    def test_always_allowed_servers_as_list(self):
        p = DhcpServerPolicy.from_dashboard(_raw(alwaysAllowedServers=["10.0.0.10"]))
        assert p.always_allowed_servers == ["10.0.0.10"]

    def test_arp_inspection_as_dict(self):
        p = DhcpServerPolicy.from_dashboard(_raw(arpInspection={"enabled": True}))
        assert p.arp_inspection == {"enabled": True}

    def test_optional_fields_default_none(self):
        p = DhcpServerPolicy.from_dashboard({"networkId": "N_abc"})
        assert p.default_policy is None
        assert p.blocked_servers is None
        assert p.arp_inspection is None

    def test_versioning_fields_not_set(self):
        p = DhcpServerPolicy.from_dashboard(_raw())
        assert p.active_from is None
        assert p.active_to is None
        assert p.last_seen is None

    def test_unknown_keys_ignored(self):
        p = DhcpServerPolicy.from_dashboard(_raw(extraKey="x"))
        assert p.network_id == "N_abc"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        p = DhcpServerPolicy.from_row(_row())
        assert p.network_id == "N_abc"
        assert p.default_policy == "block"
        assert p.blocked_servers == ["10.0.0.5"]

    def test_extra_columns_ignored(self):
        p = DhcpServerPolicy.from_row({**_row(), "pg_col": "x"})
        assert p.network_id == "N_abc"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        p = DhcpServerPolicy.from_row({**_row(), "active_from": now, "last_seen": now})
        assert p.active_from == now
        assert p.last_seen == now
        assert p.active_to is None


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        p = DhcpServerPolicy(network_id="N_abc")
        assert p.resource_path == "/networks/N_abc/switch/dhcpServerPolicy"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            DhcpServerPolicy.get("N_abc", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            DhcpServerPolicy.get("N_abc", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def test_returns_list_with_one_policy(self):
        mock_dash = MagicMock()
        mock_dash.switch.getNetworkSwitchDhcpServerPolicy.return_value = dict(_raw())
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            policies = DhcpServerPolicy.get("N_abc", source="meraki")
        assert len(policies) == 1
        assert isinstance(policies[0], DhcpServerPolicy)

    def test_network_id_passed_to_api(self):
        mock_dash = MagicMock()
        mock_dash.switch.getNetworkSwitchDhcpServerPolicy.return_value = {"networkId": "N_abc"}
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            DhcpServerPolicy.get("N_abc", source="meraki")
        mock_dash.switch.getNetworkSwitchDhcpServerPolicy.assert_called_once_with("N_abc")

    def test_network_id_injected(self):
        mock_dash = MagicMock()
        mock_dash.switch.getNetworkSwitchDhcpServerPolicy.return_value = {"defaultPolicy": "block"}
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            policies = DhcpServerPolicy.get("N_abc", source="meraki")
        assert policies[0].network_id == "N_abc"


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_returns_one_policy_when_found(self):
        engine, conn = _mock_engine(fetchone=_row())
        with patch("merakisync.database.get_engine", return_value=engine):
            policies = DhcpServerPolicy.get("N_abc", source="database")
        assert len(policies) == 1
        assert isinstance(policies[0], DhcpServerPolicy)

    def test_returns_empty_when_not_found(self):
        engine, conn = _mock_engine(fetchone=None)
        with patch("merakisync.database.get_engine", return_value=engine):
            policies = DhcpServerPolicy.get("N_abc", source="database")
        assert policies == []

    def test_network_id_in_params(self):
        engine, conn = _mock_engine(fetchone=None)
        with patch("merakisync.database.get_engine", return_value=engine):
            DhcpServerPolicy.get("N_abc", source="database")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_active_to_null_default(self):
        engine, conn = _mock_engine(fetchone=None)
        with patch("merakisync.database.get_engine", return_value=engine):
            DhcpServerPolicy.get("N_abc", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_ts_filter(self):
        engine, conn = _mock_engine(fetchone=None)
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            DhcpServerPolicy.get("N_abc", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all(self):
        engine, conn = _mock_engine(fetchone=None)
        with patch("merakisync.database.get_engine", return_value=engine):
            DhcpServerPolicy.get("N_abc", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql
