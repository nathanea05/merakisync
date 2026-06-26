from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="DeviceLldpCdp")


@dataclass()
class DeviceLldpCdp(MerakiObj):
    """CDP and LLDP neighbor data per device port — maps to meraki.device_lldp_cdp.

    Retrieved via GET /devices/{serial}/lldp_cdp. The response is keyed by local
    port number and contains nested cdp and lldp sub-dicts. _parse_response()
    flattens the structure into one row per (serial, local_port).

    No per-port API endpoint exists; resource_path returns the device-level
    collection endpoint.

    PK: (serial, local_port)
    """

    __table_name__: ClassVar[str] = "device_lldp_cdp"
    __pk__: ClassVar[tuple[str, ...]] = ("serial", "local_port")
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # PK fields — required
    serial: str
    local_port: str

    # CDP neighbor fields (all optional — absent when no CDP neighbor on the port)
    cdp_device_id: str | None = None
    cdp_port_id: str | None = None
    cdp_address: str | None = None
    cdp_management_address: str | None = None
    cdp_version: int | None = None
    cdp_vlan_id: str | None = None
    cdp_platform: str | None = None
    cdp_native_vlan: str | None = None
    cdp_capabilities: str | None = None
    cdp_vtp_management_domain: str | None = None
    cdp_system_name: str | None = None

    # LLDP neighbor fields (all optional — absent when no LLDP neighbor on the port)
    lldp_chassis_id: str | None = None
    lldp_port_id: str | None = None
    lldp_management_address: str | None = None
    lldp_management_vlan: str | None = None
    lldp_port_description: str | None = None
    lldp_system_name: str | None = None
    lldp_system_description: str | None = None
    lldp_port_vlan: str | None = None
    lldp_capabilities: str | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this device's CDP/LLDP data.

        No per-port endpoint exists. All ports are returned together via
        GET /devices/{serial}/lldp_cdp.
        """
        return f"/devices/{self.serial}/lldp_cdp"

    # ------------------------------------------------------------------
    # Parsing helper
    # ------------------------------------------------------------------

    @classmethod
    def _parse_response(cls: Type[I], serial: str, response: dict[str, Any]) -> list[I]:
        """Flatten the nested lldp_cdp response into DeviceLldpCdp instances.

        The API returns ports as a dict keyed by local port number.  CDP and LLDP
        sub-dicts are prefixed ("deviceId" → "cdpDeviceId") so camel_to_snake
        conversion in from_dashboard() produces the correct field names.
        """
        neighbors: list[I] = []
        for port_key, port_data in response.get("ports", {}).items():
            cdp = port_data.get("cdp") or {}
            lldp = port_data.get("lldp") or {}

            flat: dict[str, Any] = {
                "serial": serial,
                "localPort": port_key,
            }
            for k, v in cdp.items():
                flat[f"cdp{k[0].upper()}{k[1:]}"] = v
            for k, v in lldp.items():
                flat[f"lldp{k[0].upper()}{k[1:]}"] = v

            neighbors.append(cls.from_dashboard(flat))
        return neighbors

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @classmethod
    def get(
        cls: Type[I],
        source: Literal["database", "meraki"] = "database",
        *,
        serial: str | None = None,
        ts: datetime | Literal["all"] | None = None,
        local_port: str | None = None,
    ) -> list[I]:
        """Retrieve CDP/LLDP neighbor data.

        Args:
            source:     "meraki" or "database".
            serial:     Device serial. Required for source="meraki".
                        Optional filter for source="database".
            ts:         Timestamp filter (DB only).
            local_port: Filter by local port number.
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            if not serial:
                raise ValueError("source='meraki' requires serial.")
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            response = dashboard.devices.getDeviceLldpCdp(serial)
            neighbors = cls._parse_response(serial, response)
            if local_port:
                neighbors = [n for n in neighbors if n.local_port == local_port]
            return neighbors

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
            if local_port:
                where.append("local_port = :local_port")
                params["local_port"] = local_port

            where_sql = " AND ".join(where) if where else "TRUE"
            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {where_sql}"
                " ORDER BY serial, local_port"
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
        """Fetch CDP/LLDP neighbor data for all devices in *org_id* and upsert into the database.

        Iterates every device in the org.  Devices that do not support the endpoint
        (e.g., older firmware) are skipped with a WARNING log.
        """
        from merakisync.dashboard import get_dashboard
        dashboard = get_dashboard()

        devices = dashboard.organizations.getOrganizationDevices(org_id, total_pages="all")

        all_neighbors: list[I] = []
        for device in devices:
            serial = device.get("serial")
            if not serial:
                continue
            try:
                response = dashboard.devices.getDeviceLldpCdp(serial)
            except Exception as exc:
                logger.warning("CDP/LLDP unavailable for device %s: %s", serial, exc)
                continue
            all_neighbors.extend(cls._parse_response(serial, response))

        if not all_neighbors:
            logger.warning("No CDP/LLDP neighbors found for org %s.", org_id)
            return []

        logger.debug(
            "Upserting %d CDP/LLDP neighbor(s) for org %s.",
            len(all_neighbors),
            org_id,
        )
        counts = cls.upsert_many(all_neighbors)
        logger.info(
            "CDP/LLDP synced for org %s — %d new, %d unchanged, %d changed.",
            org_id,
            counts.get("inserted", 0),
            counts.get("updated", 0),
            counts.get("expired+inserted", 0),
        )
        return all_neighbors
