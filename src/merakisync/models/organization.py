from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Organization")


@dataclass()
class Organization(MerakiObj):
    """Meraki Organization — maps to meraki.organization."""

    __table_name__: ClassVar[str] = "organization"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # Business fields
    id: str
    name: str
    url: str
    api: dict | None = None
    licensing: dict | None = None
    cloud: dict | None = None
    management: dict | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this organization. GET /organizations/{id}"""
        return f"/organizations/{self.id}"

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @classmethod
    def get(
        cls: Type[I],
        source: Literal["database", "meraki"] = "database",
        *,
        name: str = "",
        ts: datetime | Literal["all"] | None = None,
    ) -> list[I]:
        """Retrieve organizations from Meraki Dashboard or the database.

        Args:
            source:  "meraki" or "database".
            name:    Name filter. Behaviour differs by source:
                     - "meraki": exact case-insensitive match.
                     - "database": case-insensitive substring match (ILIKE %name%).
            ts:      Timestamp filter for DB queries.
                     None  → current rows only (active_to IS NULL).
                     "all" → all versions.
                     datetime → rows active at that point in time.
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            results = dashboard.organizations.getOrganizations()
            orgs = [cls.from_dashboard(r) for r in results]
            if name:
                needle = name.strip().lower()
                orgs = [o for o in orgs if o.name.strip().lower() == needle]
            return orgs

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

            if name:
                where.append("name ILIKE :name")
                params["name"] = f"%{name}%"

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
    def sync(cls: Type[I]) -> list[I]:
        """Fetch all organizations from Meraki and upsert into the database."""
        orgs = cls.get(source="meraki")
        if not orgs:
            logger.warning("No organizations returned from Meraki.")
            return []

        counts = cls.upsert_many(orgs)
        logger.info("Organizations synced: %s", counts)
        return orgs
