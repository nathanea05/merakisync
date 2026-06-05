"""Tests for Switchport: from_dashboard, from_row, resource_path,
and get() filtering for both sources."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.switchport import Switchport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(**kwargs) -> dict:
    base = {
        "serial": "Q2SW-1234-5678",
        "portId": "1",
        "name": "Uplink",
        "enabled": True,
        "type": "trunk",
        "vlan": 1,
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    base = {
        "serial": "Q2SW-1234-5678",
        "port_id": "1",
        "name": "Uplink",
        "enabled": True,
        "type": "trunk",
        "vlan": 1,
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
    def test_port_id_mapped_from_portId(self):
        sp = Switchport.from_dashboard(_raw())
        assert sp.port_id == "1"

    def test_serial_mapped(self):
        sp = Switchport.from_dashboard(_raw())
        assert sp.serial == "Q2SW-1234-5678"

    def test_name_mapped(self):
        sp = Switchport.from_dashboard(_raw(name="Access Port"))
        assert sp.name == "Access Port"

    def test_type_mapped(self):
        sp = Switchport.from_dashboard(_raw(type="access"))
        assert sp.type == "access"

    def test_enabled_mapped(self):
        sp = Switchport.from_dashboard(_raw(enabled=False))
        assert sp.enabled is False

    def test_vlan_mapped(self):
        sp = Switchport.from_dashboard(_raw(vlan=100))
        assert sp.vlan == 100

    def test_voice_vlan_mapped(self):
        sp = Switchport.from_dashboard(_raw(voiceVlan=200))
        assert sp.voice_vlan == 200

    def test_allowed_vlans_mapped(self):
        sp = Switchport.from_dashboard(_raw(allowedVlans="1-100"))
        assert sp.allowed_vlans == "1-100"

    def test_poe_enabled_mapped(self):
        sp = Switchport.from_dashboard(_raw(poeEnabled=True))
        assert sp.poe_enabled is True

    def test_access_policy_type_mapped(self):
        sp = Switchport.from_dashboard(_raw(accessPolicyType="Open"))
        assert sp.access_policy_type == "Open"

    def test_optional_fields_default_none(self):
        sp = Switchport.from_dashboard({"serial": "S1", "portId": "1"})
        assert sp.name is None
        assert sp.tags is None
        assert sp.vlan is None
        assert sp.stp_guard is None

    def test_versioning_fields_not_set(self):
        sp = Switchport.from_dashboard(_raw())
        assert sp.active_from is None
        assert sp.active_to is None
        assert sp.last_seen is None

    def test_unknown_keys_ignored(self):
        sp = Switchport.from_dashboard(_raw(extraKey="x"))
        assert sp.serial == "Q2SW-1234-5678"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_plain_dict(self):
        sp = Switchport.from_row(_row())
        assert sp.serial == "Q2SW-1234-5678"
        assert sp.port_id == "1"

    def test_extra_columns_ignored(self):
        sp = Switchport.from_row({**_row(), "pg_col": "x"})
        assert sp.port_id == "1"

    def test_versioning_fields_preserved(self):
        now = datetime.now(tz=timezone.utc)
        sp = Switchport.from_row({**_row(), "active_from": now, "last_seen": now})
        assert sp.active_from == now
        assert sp.last_seen == now


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        sp = Switchport(serial="Q2SW-1234", port_id="3")
        assert sp.resource_path == "/devices/Q2SW-1234/switch/ports/3"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            Switchport.get(source="meraki", serial="S1", ts=datetime.now(tz=timezone.utc))

    def test_meraki_without_serial_or_org_raises(self):
        mock_dash = MagicMock()
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with pytest.raises(ValueError, match="serial or org_id"):
                Switchport.get(source="meraki")

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Switchport.get(source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki" via serial
# ---------------------------------------------------------------------------

class TestGetMerakiSerial:
    def _make_dash(self, ports):
        mock_dash = MagicMock()
        mock_dash.switch.getDeviceSwitchPorts.return_value = ports
        return mock_dash

    def test_uses_per_device_endpoint(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Switchport.get(source="meraki", serial="Q2SW-1234-5678")
        dash.switch.getDeviceSwitchPorts.assert_called_once_with("Q2SW-1234-5678")

    def test_returns_switchport_instances(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", serial="Q2SW-1234-5678")
        assert len(ports) == 1
        assert isinstance(ports[0], Switchport)

    def test_serial_injected(self):
        dash = self._make_dash([_raw()])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", serial="Q2SW-1234-5678")
        assert ports[0].serial == "Q2SW-1234-5678"

    def test_port_id_filter(self):
        dash = self._make_dash([_raw(portId="1"), _raw(portId="2")])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", serial="S1", port_id="1")
        assert len(ports) == 1
        assert ports[0].port_id == "1"


# ---------------------------------------------------------------------------
# get() — source="meraki" via org_id
# ---------------------------------------------------------------------------

class TestGetMerakiOrg:
    def _make_dash(self, response):
        mock_dash = MagicMock()
        mock_dash.switch.getOrganizationSwitchPortsBySwitch.return_value = response
        return mock_dash

    def _device_data(self, serial, ports):
        return {"serial": serial, "ports": ports}

    def test_uses_org_endpoint(self):
        dash = self._make_dash([self._device_data("S1", [_raw()])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            Switchport.get(source="meraki", org_id="org1")
        dash.switch.getOrganizationSwitchPortsBySwitch.assert_called_once_with(
            "org1", total_pages="all"
        )

    def test_serial_injected_from_device_data(self):
        dash = self._make_dash([self._device_data("S1", [_raw()])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", org_id="org1")
        assert ports[0].serial == "S1"

    def test_enabled_filter(self):
        dash = self._make_dash([self._device_data("S1", [
            _raw(portId="1", enabled=True),
            _raw(portId="2", enabled=False),
        ])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", org_id="org1", enabled=True)
        assert len(ports) == 1
        assert ports[0].port_id == "1"

    def test_port_type_filter(self):
        dash = self._make_dash([self._device_data("S1", [
            _raw(portId="1", type="access"),
            _raw(portId="2", type="trunk"),
        ])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", org_id="org1", port_type="access")
        assert len(ports) == 1
        assert ports[0].type == "access"

    def test_vlan_filter(self):
        dash = self._make_dash([self._device_data("S1", [
            _raw(portId="1", vlan=100),
            _raw(portId="2", vlan=200),
        ])])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            ports = Switchport.get(source="meraki", org_id="org1", vlan=100)
        assert len(ports) == 1
        assert ports[0].vlan == 100


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_serial_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", serial="Q2SW-1234")
        params = conn.execute.call_args.args[1]
        assert params["serial"] == "Q2SW-1234"

    def test_port_id_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", port_id="3")
        params = conn.execute.call_args.args[1]
        assert params["port_id"] == "3"

    def test_enabled_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", enabled=True)
        params = conn.execute.call_args.args[1]
        assert params["enabled"] is True

    def test_port_type_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", port_type="access")
        params = conn.execute.call_args.args[1]
        assert params["port_type"] == "access"

    def test_vlan_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", vlan=100)
        params = conn.execute.call_args.args[1]
        assert params["vlan"] == 100

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_no_filters_uses_true(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            Switchport.get(source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "TRUE" in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            ports = Switchport.get(source="database")
        assert len(ports) == 1
        assert isinstance(ports[0], Switchport)


# ---------------------------------------------------------------------------
# sync()
# ---------------------------------------------------------------------------

class TestSync:
    def _api_device(self, serial, ports):
        return {"serial": serial, "ports": ports}

    def test_sync_returns_switchport_instances(self):
        mock_dash = MagicMock()
        mock_dash.switch.getOrganizationSwitchPortsBySwitch.return_value = [
            self._api_device("S1", [_raw()])
        ]
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(Switchport, "upsert_many", return_value={"inserted": 1}):
                ports = Switchport.sync("org1")
        assert len(ports) == 1
        assert isinstance(ports[0], Switchport)

    def test_sync_empty_response_returns_empty_list(self):
        mock_dash = MagicMock()
        mock_dash.switch.getOrganizationSwitchPortsBySwitch.return_value = []
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            ports = Switchport.sync("org1")
        assert ports == []

    def test_sync_injects_serial(self):
        mock_dash = MagicMock()
        mock_dash.switch.getOrganizationSwitchPortsBySwitch.return_value = [
            self._api_device("SERIAL1", [_raw(portId="1")])
        ]
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(Switchport, "upsert_many", return_value={}):
                ports = Switchport.sync("org1")
        assert ports[0].serial == "SERIAL1"
