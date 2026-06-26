"""Tests for DeviceLldpCdp: from_dashboard, from_row, _parse_response,
resource_path, get(), and sync()."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from merakisync.models.device_lldp_cdp import DeviceLldpCdp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_response(**kwargs) -> dict:
    """Minimal valid lldp_cdp API response (one port with both CDP and LLDP)."""
    base = {
        "serial": "Q2SW-AAAA-BBBB",
        "sourceMac": "00:11:22:33:44:55",
        "ports": {
            "8": {
                "cdp": {
                    "deviceId": "Q2HP-XXXX-XXXX",
                    "portId": "Port 3",
                    "address": "1.2.3.4",
                    "managementAddress": "1.2.3.4",
                    "version": 2,
                    "vlanId": "1",
                    "platform": "cisco WS-C3560CG-8PC-S",
                    "nativeVlan": "1",
                    "capabilities": "Switch",
                    "vtpManagementDomain": "",
                    "systemName": "switch.example.com",
                },
                "lldp": {
                    "chassisId": "Q2HP-XXXX-XXXX",
                    "portId": "Port 3",
                    "managementAddress": "1.2.3.4",
                    "managementVlan": "1",
                    "portDescription": "GigabitEthernet0/1",
                    "systemName": "switch.example.com",
                    "systemDescription": "Cisco IOS Software",
                    "portVlan": "1",
                    "capabilities": "B, T",
                },
            }
        },
    }
    base.update(kwargs)
    return base


def _flat(**kwargs) -> dict:
    """Minimal flat dict suitable for from_dashboard()."""
    base = {
        "serial": "Q2SW-AAAA-BBBB",
        "localPort": "8",
    }
    base.update(kwargs)
    return base


def _row(**kwargs) -> dict:
    """Minimal valid DB row dict."""
    base = {
        "serial": "Q2SW-AAAA-BBBB",
        "local_port": "8",
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
# from_dashboard — flat dict via camel_to_snake
# ---------------------------------------------------------------------------

class TestFromDashboard:
    def test_serial_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(serial="Q2SW-1234"))
        assert n.serial == "Q2SW-1234"

    def test_local_port_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(localPort="12"))
        assert n.local_port == "12"

    def test_cdp_device_id_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpDeviceId="neighbor-serial"))
        assert n.cdp_device_id == "neighbor-serial"

    def test_cdp_port_id_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpPortId="Port 1"))
        assert n.cdp_port_id == "Port 1"

    def test_cdp_address_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpAddress="10.0.0.1"))
        assert n.cdp_address == "10.0.0.1"

    def test_cdp_management_address_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpManagementAddress="10.0.0.1"))
        assert n.cdp_management_address == "10.0.0.1"

    def test_cdp_version_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpVersion=2))
        assert n.cdp_version == 2

    def test_cdp_vlan_id_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpVlanId="10"))
        assert n.cdp_vlan_id == "10"

    def test_cdp_platform_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpPlatform="cisco WS-C3560CG-8PC-S"))
        assert n.cdp_platform == "cisco WS-C3560CG-8PC-S"

    def test_cdp_native_vlan_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpNativeVlan="1"))
        assert n.cdp_native_vlan == "1"

    def test_cdp_capabilities_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpCapabilities="Switch"))
        assert n.cdp_capabilities == "Switch"

    def test_cdp_vtp_management_domain_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpVtpManagementDomain="corp"))
        assert n.cdp_vtp_management_domain == "corp"

    def test_cdp_system_name_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(cdpSystemName="switch.corp"))
        assert n.cdp_system_name == "switch.corp"

    def test_lldp_chassis_id_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpChassisId="aa:bb:cc:dd:ee:ff"))
        assert n.lldp_chassis_id == "aa:bb:cc:dd:ee:ff"

    def test_lldp_port_id_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpPortId="Gi0/1"))
        assert n.lldp_port_id == "Gi0/1"

    def test_lldp_management_address_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpManagementAddress="10.0.0.2"))
        assert n.lldp_management_address == "10.0.0.2"

    def test_lldp_management_vlan_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpManagementVlan="1"))
        assert n.lldp_management_vlan == "1"

    def test_lldp_port_description_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpPortDescription="GigabitEthernet0/1"))
        assert n.lldp_port_description == "GigabitEthernet0/1"

    def test_lldp_system_name_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpSystemName="router.corp"))
        assert n.lldp_system_name == "router.corp"

    def test_lldp_system_description_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpSystemDescription="Cisco IOS"))
        assert n.lldp_system_description == "Cisco IOS"

    def test_lldp_port_vlan_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpPortVlan="100"))
        assert n.lldp_port_vlan == "100"

    def test_lldp_capabilities_mapped(self):
        n = DeviceLldpCdp.from_dashboard(_flat(lldpCapabilities="B, T"))
        assert n.lldp_capabilities == "B, T"

    def test_optional_fields_default_none(self):
        n = DeviceLldpCdp.from_dashboard(_flat())
        assert n.cdp_device_id is None
        assert n.lldp_chassis_id is None
        assert n.cdp_version is None

    def test_unknown_fields_ignored(self):
        n = DeviceLldpCdp.from_dashboard(_flat(unknownFutureField="ignored"))
        assert n.serial == "Q2SW-AAAA-BBBB"

    def test_versioning_fields_not_set(self):
        n = DeviceLldpCdp.from_dashboard(_flat())
        assert n.active_from is None
        assert n.active_to is None
        assert n.last_seen is None


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_single_port_both_protocols(self):
        resp = _api_response()
        neighbors = DeviceLldpCdp._parse_response("Q2SW-AAAA-BBBB", resp)
        assert len(neighbors) == 1
        n = neighbors[0]
        assert n.serial == "Q2SW-AAAA-BBBB"
        assert n.local_port == "8"
        assert n.cdp_device_id == "Q2HP-XXXX-XXXX"
        assert n.cdp_version == 2
        assert n.lldp_chassis_id == "Q2HP-XXXX-XXXX"
        assert n.lldp_capabilities == "B, T"

    def test_multiple_ports(self):
        resp = {
            "ports": {
                "1": {"cdp": {"deviceId": "neighbor-A"}, "lldp": {}},
                "2": {"cdp": {"deviceId": "neighbor-B"}, "lldp": {}},
            }
        }
        neighbors = DeviceLldpCdp._parse_response("S1", resp)
        assert len(neighbors) == 2
        serials = {n.serial for n in neighbors}
        ports = {n.local_port for n in neighbors}
        assert serials == {"S1"}
        assert ports == {"1", "2"}

    def test_cdp_only_port(self):
        resp = {"ports": {"5": {"cdp": {"deviceId": "neighbor-X"}}}}
        neighbors = DeviceLldpCdp._parse_response("S1", resp)
        assert len(neighbors) == 1
        assert neighbors[0].cdp_device_id == "neighbor-X"
        assert neighbors[0].lldp_chassis_id is None

    def test_lldp_only_port(self):
        resp = {"ports": {"3": {"lldp": {"chassisId": "aa:bb:cc"}}}}
        neighbors = DeviceLldpCdp._parse_response("S1", resp)
        assert len(neighbors) == 1
        assert neighbors[0].lldp_chassis_id == "aa:bb:cc"
        assert neighbors[0].cdp_device_id is None

    def test_empty_ports_returns_empty_list(self):
        resp = {"ports": {}}
        assert DeviceLldpCdp._parse_response("S1", resp) == []

    def test_missing_ports_key_returns_empty_list(self):
        assert DeviceLldpCdp._parse_response("S1", {}) == []

    def test_none_cdp_sub_dict_handled(self):
        resp = {"ports": {"8": {"cdp": None, "lldp": {"chassisId": "mac"}}}}
        neighbors = DeviceLldpCdp._parse_response("S1", resp)
        assert len(neighbors) == 1
        assert neighbors[0].cdp_device_id is None
        assert neighbors[0].lldp_chassis_id == "mac"

    def test_none_lldp_sub_dict_handled(self):
        resp = {"ports": {"8": {"cdp": {"deviceId": "nbr"}, "lldp": None}}}
        neighbors = DeviceLldpCdp._parse_response("S1", resp)
        assert len(neighbors) == 1
        assert neighbors[0].cdp_device_id == "nbr"
        assert neighbors[0].lldp_chassis_id is None

    def test_serial_injected_correctly(self):
        resp = {"ports": {"1": {"cdp": {"deviceId": "x"}}}}
        neighbors = DeviceLldpCdp._parse_response("INJECTED-SERIAL", resp)
        assert neighbors[0].serial == "INJECTED-SERIAL"


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_basic_row(self):
        n = DeviceLldpCdp.from_row(_row())
        assert n.serial == "Q2SW-AAAA-BBBB"
        assert n.local_port == "8"

    def test_cdp_fields_from_row(self):
        n = DeviceLldpCdp.from_row(_row(
            cdp_device_id="nbr", cdp_port_id="Port 1", cdp_version=2,
        ))
        assert n.cdp_device_id == "nbr"
        assert n.cdp_port_id == "Port 1"
        assert n.cdp_version == 2

    def test_lldp_fields_from_row(self):
        n = DeviceLldpCdp.from_row(_row(
            lldp_chassis_id="aa:bb:cc", lldp_system_name="router.corp",
        ))
        assert n.lldp_chassis_id == "aa:bb:cc"
        assert n.lldp_system_name == "router.corp"

    def test_versioning_fields_from_row(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n = DeviceLldpCdp.from_row(_row(active_from=ts, active_to=None, last_seen=ts))
        assert n.active_from == ts
        assert n.active_to is None
        assert n.last_seen == ts

    def test_extra_columns_ignored(self):
        n = DeviceLldpCdp.from_row({**_row(), "pg_internal": "ignored"})
        assert n.serial == "Q2SW-AAAA-BBBB"


# ---------------------------------------------------------------------------
# _data_fields
# ---------------------------------------------------------------------------

class TestDataFields:
    def test_excludes_pk(self):
        n = DeviceLldpCdp.from_row(_row())
        data = n._data_fields()
        assert "serial" not in data
        assert "local_port" not in data

    def test_excludes_versioning_fields(self):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        n = DeviceLldpCdp.from_row(_row(active_from=ts, active_to=None, last_seen=ts))
        data = n._data_fields()
        assert "active_from" not in data
        assert "active_to" not in data
        assert "last_seen" not in data

    def test_includes_cdp_and_lldp_fields(self):
        n = DeviceLldpCdp.from_row(_row(cdp_device_id="nbr", lldp_chassis_id="mac"))
        data = n._data_fields()
        assert data["cdp_device_id"] == "nbr"
        assert data["lldp_chassis_id"] == "mac"


# ---------------------------------------------------------------------------
# resource_path
# ---------------------------------------------------------------------------

class TestResourcePath:
    def test_resource_path(self):
        n = DeviceLldpCdp(serial="Q2SW-1234-5678", local_port="8")
        assert n.resource_path == "/devices/Q2SW-1234-5678/lldp_cdp"


# ---------------------------------------------------------------------------
# get() — validation
# ---------------------------------------------------------------------------

class TestGetValidation:
    def test_ts_with_meraki_raises(self):
        with pytest.raises(ValueError, match="Timestamp"):
            DeviceLldpCdp.get(source="meraki", serial="S1", ts=datetime.now(tz=timezone.utc))

    def test_meraki_without_serial_raises(self):
        with pytest.raises(ValueError, match="serial"):
            DeviceLldpCdp.get(source="meraki")

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            DeviceLldpCdp.get(source="invalid")  # type: ignore


# ---------------------------------------------------------------------------
# get() — source="meraki"
# ---------------------------------------------------------------------------

class TestGetMeraki:
    def _make_dash(self, resp):
        mock_dash = MagicMock()
        mock_dash.devices.getDeviceLldpCdp.return_value = resp
        return mock_dash

    def test_returns_instances(self):
        dash = self._make_dash(_api_response())
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            neighbors = DeviceLldpCdp.get(source="meraki", serial="Q2SW-AAAA-BBBB")
        assert len(neighbors) == 1
        assert isinstance(neighbors[0], DeviceLldpCdp)

    def test_uses_correct_endpoint(self):
        dash = self._make_dash(_api_response())
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            DeviceLldpCdp.get(source="meraki", serial="Q2SW-AAAA-BBBB")
        dash.devices.getDeviceLldpCdp.assert_called_once_with("Q2SW-AAAA-BBBB")

    def test_local_port_filter(self):
        resp = {
            "ports": {
                "8": {"cdp": {"deviceId": "nbr-A"}},
                "9": {"cdp": {"deviceId": "nbr-B"}},
            }
        }
        dash = self._make_dash(resp)
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            neighbors = DeviceLldpCdp.get(source="meraki", serial="S1", local_port="8")
        assert len(neighbors) == 1
        assert neighbors[0].local_port == "8"

    def test_empty_ports_returns_empty_list(self):
        dash = self._make_dash({"ports": {}})
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert DeviceLldpCdp.get(source="meraki", serial="S1") == []


# ---------------------------------------------------------------------------
# get() — source="database"
# ---------------------------------------------------------------------------

class TestGetDatabase:
    def test_active_to_null_default(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            DeviceLldpCdp.get(source="database")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" in sql

    def test_serial_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            DeviceLldpCdp.get(source="database", serial="Q2SW-1234")
        params = conn.execute.call_args.args[1]
        assert params["serial"] == "Q2SW-1234"

    def test_local_port_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            DeviceLldpCdp.get(source="database", local_port="8")
        params = conn.execute.call_args.args[1]
        assert params["local_port"] == "8"

    def test_ts_filter(self):
        engine, conn = _mock_engine([])
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("merakisync.database.get_engine", return_value=engine):
            DeviceLldpCdp.get(source="database", ts=ts)
        params = conn.execute.call_args.args[1]
        assert params["ts"] == ts

    def test_ts_all_omits_active_to_filter(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            DeviceLldpCdp.get(source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "active_to IS NULL" not in sql

    def test_no_filters_uses_true(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            DeviceLldpCdp.get(source="database", ts="all")
        sql = str(conn.execute.call_args.args[0])
        assert "TRUE" in sql

    def test_results_mapped_to_instances(self):
        engine, conn = _mock_engine([_row()])
        with patch("merakisync.database.get_engine", return_value=engine):
            neighbors = DeviceLldpCdp.get(source="database")
        assert len(neighbors) == 1
        assert isinstance(neighbors[0], DeviceLldpCdp)

    def test_empty_result_returns_empty_list(self):
        engine, conn = _mock_engine([])
        with patch("merakisync.database.get_engine", return_value=engine):
            assert DeviceLldpCdp.get(source="database") == []


# ---------------------------------------------------------------------------
# sync()
# ---------------------------------------------------------------------------

class TestSync:
    def _make_dash(self, devices, lldp_cdp_response=None):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationDevices.return_value = devices
        mock_dash.devices.getDeviceLldpCdp.return_value = (
            lldp_cdp_response if lldp_cdp_response is not None else _api_response()
        )
        return mock_dash

    def test_returns_instances(self):
        dash = self._make_dash([{"serial": "S1"}])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            with patch.object(DeviceLldpCdp, "upsert_many", return_value={"inserted": 1}):
                neighbors = DeviceLldpCdp.sync("org1")
        assert len(neighbors) == 1
        assert isinstance(neighbors[0], DeviceLldpCdp)

    def test_iterates_all_devices(self):
        dash = self._make_dash([{"serial": "S1"}, {"serial": "S2"}])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            with patch.object(DeviceLldpCdp, "upsert_many", return_value={}):
                DeviceLldpCdp.sync("org1")
        assert dash.devices.getDeviceLldpCdp.call_count == 2

    def test_skips_device_without_serial(self):
        dash = self._make_dash([{"serial": "S1"}, {"model": "MR33"}])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            with patch.object(DeviceLldpCdp, "upsert_many", return_value={}):
                DeviceLldpCdp.sync("org1")
        assert dash.devices.getDeviceLldpCdp.call_count == 1

    def test_skips_device_on_api_error(self):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationDevices.return_value = [
            {"serial": "S1"}, {"serial": "S2"}
        ]
        mock_dash.devices.getDeviceLldpCdp.side_effect = [
            Exception("404 Not Found"),
            _api_response(),
        ]
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            with patch.object(DeviceLldpCdp, "upsert_many", return_value={}):
                neighbors = DeviceLldpCdp.sync("org1")
        assert len(neighbors) == 1

    def test_no_devices_returns_empty_list(self):
        dash = self._make_dash([])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            assert DeviceLldpCdp.sync("org1") == []

    def test_all_devices_fail_returns_empty_list(self):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizationDevices.return_value = [{"serial": "S1"}]
        mock_dash.devices.getDeviceLldpCdp.side_effect = Exception("error")
        with patch("merakisync.dashboard.get_dashboard", return_value=mock_dash):
            assert DeviceLldpCdp.sync("org1") == []

    def test_calls_upsert_many(self):
        dash = self._make_dash([{"serial": "S1"}])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            with patch.object(DeviceLldpCdp, "upsert_many", return_value={"inserted": 1}) as mock_upsert:
                DeviceLldpCdp.sync("org1")
        mock_upsert.assert_called_once()

    def test_uses_org_devices_endpoint(self):
        dash = self._make_dash([{"serial": "S1"}])
        with patch("merakisync.dashboard.get_dashboard", return_value=dash):
            with patch.object(DeviceLldpCdp, "upsert_many", return_value={}):
                DeviceLldpCdp.sync("org1")
        dash.organizations.getOrganizationDevices.assert_called_once_with("org1", total_pages="all")
