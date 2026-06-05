"""Tests for L3FirewallRule: from_dashboard, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.l3_firewall_rule import L3FirewallRule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_rule(**kwargs) -> dict:
    """Single rule dict as returned by the Meraki API (inside rules[])."""
    base = {
        "comment": "Allow web",
        "policy": "allow",
        "protocol": "tcp",
        "destPort": "80,443",
        "destCidr": "any",
        "srcPort": "Any",
        "srcCidr": "any",
        "syslogEnabled": False,
    }
    base.update(kwargs)
    return base


def _raw_with_injected(rule_order=0, network_id="N_abc", **rule_kwargs) -> dict:
    """Rule dict with injected PK fields (as would be passed to from_dashboard)."""
    d = _raw_rule(**rule_kwargs)
    d["networkId"] = network_id
    d["ruleOrder"] = rule_order
    return d


def _row(**kwargs) -> dict:
    base = {
        "network_id": "N_abc",
        "rule_order": 0,
        "comment": "Allow web",
        "policy": "allow",
        "protocol": "tcp",
        "dest_port": "80,443",
        "dest_cidr": "any",
        "src_port": "Any",
        "src_cidr": "any",
        "syslog_enabled": False,
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
    def test_network_id_from_networkId(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected())
        assert r.network_id == "N_abc"

    def test_rule_order_from_ruleOrder(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(rule_order=3))
        assert r.rule_order == 3

    def test_policy_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(policy="deny"))
        assert r.policy == "deny"

    def test_protocol_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(protocol="udp"))
        assert r.protocol == "udp"

    def test_dest_port_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(destPort="443"))
        assert r.dest_port == "443"

    def test_dest_cidr_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(destCidr="192.168.1.0/24"))
        assert r.dest_cidr == "192.168.1.0/24"

    def test_src_port_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(srcPort="any"))
        assert r.src_port == "any"

    def test_src_cidr_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(srcCidr="10.0.0.0/8"))
        assert r.src_cidr == "10.0.0.0/8"

    def test_syslog_enabled_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(syslogEnabled=True))
        assert r.syslog_enabled is True

    def test_comment_mapped(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(comment="Deny all"))
        assert r.comment == "Deny all"

    def test_optional_fields_default_none(self):
        r = L3FirewallRule.from_dashboard({"networkId": "N_abc", "ruleOrder": 0})
        assert r.policy is None
        assert r.protocol is None
        assert r.dest_port is None

    def test_versioning_fields_not_set(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected())
        assert r.active_from is None
        assert r.active_to is None
        assert r.last_seen is None

    def test_unknown_keys_ignored(self):
        r = L3FirewallRule.from_dashboard(_raw_with_injected(extraKey="x"))
        assert r.network_id == "N_abc"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        r = L3FirewallRule.from_row(_row())
        assert r.network_id == "N_abc"
        assert r.rule_order == 0
        assert r.policy == "allow"
        assert r.protocol == "tcp"

    def test_extra_columns_ignored(self):
        r = L3FirewallRule.from_row({**_row(), "pg_col": "x"})
        assert r.rule_order == 0

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        r = L3FirewallRule.from_row({**_row(), "active_from": now, "last_seen": now})
        assert r.active_from == now
        assert r.last_seen == now
        assert r.active_to is None


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        r = L3FirewallRule(network_id="N_abc", rule_order=0)
        assert r.resource_path == "/networks/N_abc/appliance/firewall/l3FirewallRules"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            L3FirewallRule.get("N_abc", source="meraki", ts=datetime.now(tz=timezone.utc))

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            L3FirewallRule.get("N_abc", source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, rules):
        mock_dash = MagicMock()
        mock_dash.appliance.getNetworkApplianceFirewallL3FirewallRules.return_value = {
            "rules": rules
        }
        return mock_dash

    def test_returns_rule_instances(self):
        dash = self._make_dash([_raw_rule()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            rules = L3FirewallRule.get("N_abc", source="meraki")
        assert len(rules) == 1
        assert isinstance(rules[0], L3FirewallRule)

    def test_rule_order_assigned_by_index(self):
        dash = self._make_dash([_raw_rule(), _raw_rule(comment="Rule 2")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            rules = L3FirewallRule.get("N_abc", source="meraki")
        assert rules[0].rule_order == 0
        assert rules[1].rule_order == 1

    def test_network_id_injected(self):
        dash = self._make_dash([_raw_rule()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            rules = L3FirewallRule.get("N_abc", source="meraki")
        assert rules[0].network_id == "N_abc"

    def test_empty_rules_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert L3FirewallRule.get("N_abc", source="meraki") == []

    def test_network_id_passed_to_api(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            L3FirewallRule.get("N_abc", source="meraki")
        dash.appliance.getNetworkApplianceFirewallL3FirewallRules.assert_called_once_with("N_abc")


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_network_id_always_in_params(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database")
        params = conn.execute.call_args.args[1]
        assert params["network_id"] == "N_abc"

    def test_policy_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database", policy="deny")
        params = conn.execute.call_args.args[1]
        assert params["policy"] == "deny"

    def test_protocol_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database", protocol="tcp")
        params = conn.execute.call_args.args[1]
        assert params["protocol"] == "tcp"

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            rules = L3FirewallRule.get("N_abc", source="database")
        assert len(rules) == 1
        assert isinstance(rules[0], L3FirewallRule)

    def test_ordered_by_rule_order(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            L3FirewallRule.get("N_abc", source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "ORDER BY rule_order" in sql
