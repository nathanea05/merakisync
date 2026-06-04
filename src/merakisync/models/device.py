from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj
from merakisync.utils.filter_array import filter_array

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Device")


@dataclass()
class Device(MerakiObj):
    """Meraki Device — maps to meraki.device."""

    __table_name__: ClassVar[str] = "device"
    __pk__: ClassVar[tuple[str, ...]] = ("serial",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # Business fields
    serial: str
    name: str | None = None
    network_id: str | None = None
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    model: str | None = None
    mac: str | None = None
    lan_ip: str | None = None
    firmware: str | None = None
    floor_plan_id: str | None = None
    details: list[dict] | None = None
    beacon_id_params: dict | None = None
    status: str | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this device. GET /devices/{serial}"""
        return f"/devices/{self.serial}"

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @classmethod
    def get(
        cls: Type[I],
        org_id: str,
        source: Literal["database", "meraki"] = "database",
        *,
        ts: datetime | Literal["all"] | None = None,
        serial: str = "",
        name: str = "",
        network_id: str = "",
        tags_include: list[str] | None = None,
        tags_exclude: list[str] | None = None,
        status: str = "",
        model: str = "",
        product_types_include: list[Literal["appliance", "switch", "wireless"]] | None = None,
        product_types_exclude: list[Literal["appliance", "switch", "wireless"]] | None = None,
    ) -> list[I]:
        """Retrieve devices for an organization.

        Args:
            org_id:  Meraki organization ID.
            source:  "meraki" or "database".
            ts:      Timestamp filter (DB only).
            serial:  Filter by device serial.
            name:    Name filter. Behaviour differs by source:
                     - "meraki": passed to the API (exact match, server-side).
                     - "database": case-insensitive substring match (ILIKE %name%).
            network_id: Filter by network ID.
            tags_include:          All tags must be present (applied client-side for Meraki).
            tags_exclude:          None of these tags may be present.
            status:  Filter by device status (applied client-side for Meraki).
            model:   Filter by model string.
            product_types_include: Passed to Meraki API; also used for DB model-prefix filter.
            product_types_exclude: Client-side only.
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        tags_include = tags_include or []
        tags_exclude = tags_exclude or []
        product_types_include = product_types_include or []
        product_types_exclude = product_types_exclude or []

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()

            api_kwargs: dict = {"organizationId": org_id, "total_pages": "all"}
            if serial:
                api_kwargs["serial"] = serial
            if network_id:
                api_kwargs["networkIds"] = [network_id]
            if product_types_include:
                api_kwargs["productTypes"] = product_types_include
            if tags_include:
                api_kwargs["tags"] = tags_include
            if name:
                api_kwargs["name"] = name
            if model:
                api_kwargs["model"] = model

            raw = dashboard.organizations.getOrganizationDevices(**api_kwargs)
            devices = [cls.from_dashboard(r) for r in raw]

            _prefix_map = {"appliance": "MX", "switch": "MS", "wireless": "MR"}
            excl_prefixes = [
                _prefix_map[pt] for pt in product_types_exclude if pt in _prefix_map
            ]

            filtered: list[I] = []
            for dev in devices:
                if not filter_array(
                    values=set(dev.tags or []),
                    include=tags_include,
                    exclude=tags_exclude,
                ):
                    continue
                if status and dev.status != status:
                    continue
                if excl_prefixes and any(
                    (dev.model or "").upper().startswith(p) for p in excl_prefixes
                ):
                    continue
                filtered.append(dev)
            return filtered

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
            if network_id:
                where.append("network_id = :network_id")
                params["network_id"] = network_id
            if name:
                where.append("name ILIKE :name")
                params["name"] = f"%{name}%"
            if model:
                where.append("model ILIKE :model")
                params["model"] = f"%{model}%"
            if status:
                where.append("status = :status")
                params["status"] = status
            if tags_include:
                where.append("tags ?& :tags_include")
                params["tags_include"] = tags_include
            if tags_exclude:
                where.append("NOT (tags ?| :tags_exclude)")
                params["tags_exclude"] = tags_exclude

            prefix_map = {"appliance": "MX", "switch": "MS", "wireless": "MR"}

            if product_types_include:
                incl_clauses = []
                for i, pt in enumerate(product_types_include):
                    prefix = prefix_map.get(pt)
                    if prefix:
                        k = f"incl_prefix_{i}"
                        incl_clauses.append(f"model ILIKE :{k}")
                        params[k] = f"{prefix}%"
                if incl_clauses:
                    where.append("(" + " OR ".join(incl_clauses) + ")")

            if product_types_exclude:
                for i, pt in enumerate(product_types_exclude):
                    prefix = prefix_map.get(pt)
                    if prefix:
                        k = f"excl_prefix_{i}"
                        where.append(f"model NOT ILIKE :{k}")
                        params[k] = f"{prefix}%"

            where_sql = " AND ".join(where) if where else "TRUE"
            sql = text(f"SELECT * FROM {cls._qualified()} WHERE {where_sql}")

            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], org_id: str) -> list[I]:
        """Fetch all devices for *org_id* from Meraki and upsert into the database."""
        devices = cls.get(org_id, source="meraki")
        if not devices:
            logger.warning("No devices returned for org %s.", org_id)
            return []

        counts = cls.upsert_many(devices)
        logger.info("Devices synced for org %s: %s", org_id, counts)
        return devices
