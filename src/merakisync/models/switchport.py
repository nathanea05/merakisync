from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Switchport")


@dataclass()
class Switchport(MerakiObj):
    """Meraki MS switch port configuration — maps to meraki.switchport.

    Retrieved via GET /devices/{serial}/switch/ports.
    The serial is returned in the response when iterating per-device, but
    is not included in the individual port object — it must be injected
    before calling from_dashboard().

    PK: (serial, port_id)
    """

    __table_name__: ClassVar[str] = "switchport"
    __pk__: ClassVar[tuple[str, ...]] = ("serial", "port_id")
    __mapping_override__: ClassVar[dict[str, str]] = {
        "port_id": "portId",
        "poe_enabled": "poeEnabled",
        "isolation_enabled": "isolationEnabled",
        "rstp_enabled": "rstpEnabled",
        "stp_guard": "stpGuard",
        "link_negotiation": "linkNegotiation",
        "port_schedule_id": "portScheduleId",
        "access_policy_type": "accessPolicyType",
        "access_policy_number": "accessPolicyNumber",
        "mac_allow_list": "macAllowList",
        "sticky_mac_allow_list": "stickyMacAllowList",
        "sticky_mac_allow_list_limit": "stickyMacAllowListLimit",
        "storm_control_enabled": "stormControlEnabled",
        "adaptive_policy_group_id": "adaptivePolicyGroupId",
        "peer_sgt_capable": "peerSgtCapable",
        "flexible_stacking_enabled": "flexibleStackingEnabled",
        "dai_trusted": "daiTrusted",
        "voice_vlan": "voiceVlan",
        "allowed_vlans": "allowedVlans",
    }

    # Business fields — serial is injected; port_id comes from the API
    serial: str
    port_id: str
    name: str | None = None
    tags: list[str] | None = None
    enabled: bool | None = None
    poe_enabled: bool | None = None
    type: str | None = None          # "access" | "trunk" | "routed" | etc.
    vlan: int | None = None
    voice_vlan: int | None = None
    allowed_vlans: str | None = None
    isolation_enabled: bool | None = None
    rstp_enabled: bool | None = None
    stp_guard: str | None = None
    link_negotiation: str | None = None
    port_schedule_id: str | None = None
    udld: str | None = None
    access_policy_type: str | None = None
    access_policy_number: int | None = None
    mac_allow_list: list[str] | None = None
    sticky_mac_allow_list: list[str] | None = None
    sticky_mac_allow_list_limit: int | None = None
    storm_control_enabled: bool | None = None
    adaptive_policy_group_id: str | None = None
    peer_sgt_capable: bool | None = None
    flexible_stacking_enabled: bool | None = None
    dai_trusted: bool | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this switchport. GET /devices/{serial}/switch/ports/{portId}"""
        return f"/devices/{self.serial}/switch/ports/{self.port_id}"

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @classmethod
    def get(
        cls: Type[I],
        serial: str,
        source: Literal["database", "meraki"] = "database",
        *,
        ts: datetime | Literal["all"] | None = None,
        port_id: str | None = None,
        enabled: bool | None = None,
        port_type: str | None = None,
        vlan: int | None = None,
    ) -> list[I]:
        """Retrieve switchports for a device serial.

        Args:
            serial:     Device serial number.
            source:     "meraki" or "database".
            ts:         Timestamp filter (DB only).
            port_id:    Filter by specific port ID.
            enabled:    Filter by enabled state (DB only).
            port_type:  Filter by port type — "access", "trunk", etc. (DB only).
            vlan:       Filter by VLAN ID (DB only).
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            raw_ports = dashboard.switch.getDeviceSwitchPorts(serial)
            ports: list[I] = []
            for raw in raw_ports:
                flat = dict(raw)
                flat["serial"] = serial
                port = cls.from_dashboard(flat)
                if port_id and port.port_id != port_id:
                    continue
                ports.append(port)
            return ports

        if source == "database":
            from merakisync.database import get_engine
            engine = get_engine()
            where: list[str] = ["serial = :serial"]
            params: dict = {"serial": serial}

            if ts and ts != "all":
                where += ["active_from <= :ts", "(active_to > :ts OR active_to IS NULL)"]
                params["ts"] = ts
            elif ts != "all":
                where.append("active_to IS NULL")

            if port_id:
                where.append("port_id = :port_id")
                params["port_id"] = port_id
            if enabled is not None:
                where.append("enabled = :enabled")
                params["enabled"] = enabled
            if port_type:
                where.append("type = :port_type")
                params["port_type"] = port_type
            if vlan is not None:
                where.append("vlan = :vlan")
                params["vlan"] = vlan

            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)}"
                " ORDER BY port_id"
            )
            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], serial: str) -> list[I]:
        """Fetch all ports for device *serial* from Meraki and upsert into the database."""
        ports = cls.get(serial, source="meraki")
        if not ports:
            logger.debug("No switchports returned for device %s.", serial)
            return []

        counts = cls.upsert_many(ports)
        logger.debug("Switchports synced for device %s: %s", serial, counts)
        return ports
