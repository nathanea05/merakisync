from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj
from merakisync.utils.filter_array import filter_array

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Network")


@dataclass(frozen=True, slots=True)
class Network(MerakiObj):
    """Meraki Network — maps to meraki.network."""

    __table_name__: ClassVar[str] = "network"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # Business fields
    id: str
    organization_id: str
    name: str
    product_types: list | None = None
    time_zone: str | None = None
    tags: list | None = None
    enrollment_string: str | None = None
    url: str | None = None
    notes: str | None = None
    is_bound_to_config_template: bool | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this network. GET /networks/{id}"""
        return f"/networks/{self.id}"

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
        name: str = "",
        network_id: str = "",
        tags_include: list[str] | None = None,
        tags_exclude: list[str] | None = None,
        product_types_include: list[str] | None = None,
        product_types_exclude: list[str] | None = None,
    ) -> list[I]:
        """Retrieve networks for an organization.

        Args:
            org_id:   Meraki organization ID (required for source='meraki').
            source:   "meraki" or "database".
            ts:       Timestamp filter (DB only).
            name:     Exact-name filter for Meraki; ILIKE filter for DB.
            network_id: Filter by network ID.
            tags_include:          All of these tags must be present.
            tags_exclude:          None of these tags may be present.
            product_types_include: All of these product types must be present.
            product_types_exclude: None of these product types may be present.
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
            raw = dashboard.organizations.getOrganizationNetworks(org_id, total_pages="all")
            networks = [cls.from_dashboard(r) for r in raw]

            filtered: list[I] = []
            for net in networks:
                if name and net.name != name:
                    continue
                if network_id and net.id != network_id:
                    continue
                if not filter_array(
                    values=set(net.tags or []),
                    include=tags_include,
                    exclude=tags_exclude,
                ):
                    continue
                if not filter_array(
                    values=set(net.product_types or []),
                    include=product_types_include,
                    exclude=product_types_exclude,
                ):
                    continue
                filtered.append(net)

            filtered.sort(key=lambda n: n.name)
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

            if org_id:
                where.append("organization_id = :org_id")
                params["org_id"] = org_id

            if name:
                where.append("name ILIKE :name")
                params["name"] = f"%{name}%"

            if network_id:
                where.append("id = :network_id")
                params["network_id"] = network_id

            if tags_include:
                where.append("tags ?& :tags_include")
                params["tags_include"] = tags_include

            if tags_exclude:
                where.append("NOT (tags ?| :tags_exclude)")
                params["tags_exclude"] = tags_exclude

            where_sql = " AND ".join(where) if where else "TRUE"
            sql = text(f"SELECT * FROM {cls._qualified()} WHERE {where_sql} ORDER BY name")

            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], org_id: str) -> list[I]:
        """Fetch all networks for *org_id* from Meraki and upsert into the database."""
        networks = cls.get(org_id, source="meraki")
        if not networks:
            logger.warning("No networks returned for org %s.", org_id)
            return []

        counts = cls.upsert_many(networks)
        logger.info("Networks synced for org %s: %s", org_id, counts)
        return networks
