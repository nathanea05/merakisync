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
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # Business fields — serial is injected; port_id comes from the API.
    # Fields are limited to those returned by getOrganizationSwitchPortsBySwitch.
    # Fields only available via the per-device endpoint (isolationEnabled,
    # stormControlEnabled, daiTrusted, udld, etc.) are intentionally omitted.
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
    rstp_enabled: bool | None = None
    stp_guard: str | None = None
    link_negotiation: str | None = None
    access_policy_type: str | None = None
    sticky_mac_allow_list: list[str] | None = None
    sticky_mac_allow_list_limit: int | None = None

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
        source: Literal["database", "meraki"] = "database",
        *,
        org_id: str | None = None,
        serial: str | None = None,
        ts: datetime | Literal["all"] | None = None,
        port_id: str | None = None,
        enabled: bool | None = None,
        port_type: str | None = None,
        vlan: int | None = None,
    ) -> list[I]:
        """Retrieve switchports from Meraki or the database.

        Args:
            source:     "meraki" or "database".
            org_id:     Required for source="meraki" when serial is not provided.
                        Uses GET /organizations/{org}/switch/ports/bySwitch.
            serial:     Device serial number.  When provided with source="meraki",
                        uses the faster per-device endpoint instead of the org call.
                        Optional filter for source="database".
            ts:         Timestamp filter (DB only).
            port_id:    Filter by port ID.
            enabled:    Filter by enabled state.
            port_type:  Filter by port type — "access", "trunk", etc.
            vlan:       Filter by access VLAN ID.
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()

            if serial:
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

            if org_id:
                response = dashboard.switch.getOrganizationSwitchPortsBySwitch(
                    org_id, total_pages="all"
                )
                ports = []
                for device_data in response:
                    dev_serial = device_data.get("serial", "")
                    for raw_port in device_data.get("ports", []):
                        flat = dict(raw_port)
                        flat["serial"] = dev_serial
                        port = cls.from_dashboard(flat)
                        if port_id and port.port_id != port_id:
                            continue
                        if enabled is not None and port.enabled != enabled:
                            continue
                        if port_type and port.type != port_type:
                            continue
                        if vlan is not None and port.vlan != vlan:
                            continue
                        ports.append(port)
                return ports

            raise ValueError("source='meraki' requires either serial or org_id.")

        if source == "database":
            from merakisync.database import get_engine
            engine = get_engine()
            where: list[str] = []
            params: dict = {}

            if ts and ts != "all":
                where += ["active_from <= :ts", "(active_to > :ts OR active_to IS NULL)"]
                params["ts"] = ts
            elif ts != "all":
                where.append("active_to IS NULL")

            if serial:
                where.append("serial = :serial")
                params["serial"] = serial
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

            where_sql = " AND ".join(where) if where else "TRUE"
            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {where_sql}"
                " ORDER BY serial, port_id"
            )
            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], org_id: str) -> list[I]:
        """Fetch all switchports for *org_id* in a single API call and upsert into the database."""
        from merakisync.dashboard import get_dashboard
        dashboard = get_dashboard()

        response = dashboard.switch.getOrganizationSwitchPortsBySwitch(
            org_id, total_pages="all"
        )

        ports: list[I] = []
        for device_data in response:
            serial = device_data.get("serial", "")
            for raw_port in device_data.get("ports", []):
                flat = dict(raw_port)
                flat["serial"] = serial
                ports.append(cls.from_dashboard(flat))

        if not ports:
            logger.warning("No switchports returned for org %s.", org_id)
            return []

        logger.debug(
            "Upserting %d switchport(s) across %d device(s) for org %s.",
            len(ports),
            len(response),
            org_id,
        )
        counts = cls.upsert_many(ports)
        logger.info(
            "Switchports synced for org %s — %d new, %d unchanged, %d changed.",
            org_id,
            counts.get("inserted", 0),
            counts.get("updated", 0),
            counts.get("expired+inserted", 0),
        )
        return ports
