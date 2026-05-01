from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="DhcpServerPolicy")


@dataclass(frozen=True, slots=True)
class DhcpServerPolicy(MerakiObj):
    """Meraki switch DHCP server policy — maps to meraki.dhcp_server_policy.

    Retrieved via GET /networks/{networkId}/switch/dhcpServerPolicy.
    The network_id is not returned by the API and must be injected before
    calling from_dashboard().
    """

    __table_name__: ClassVar[str] = "dhcp_server_policy"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # Business fields
    network_id: str
    default_policy: str | None = None
    blocked_servers: list[str] | None = None
    allowed_servers: list[str] | None = None
    always_allowed_servers: list[str] | None = None
    arp_inspection: dict | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @classmethod
    def get(
        cls: Type[I],
        network_id: str,
        source: Literal["database", "meraki"] = "database",
        *,
        ts: datetime | Literal["all"] | None = None,
    ) -> I | None:
        """Retrieve the DHCP server policy for a single network.

        Args:
            network_id: Meraki network ID.
            source:     "meraki" or "database".
            ts:         Timestamp filter (DB only).
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            raw = dashboard.switch.getNetworkSwitchDhcpServerPolicy(network_id)
            raw["networkId"] = network_id
            return cls.from_dashboard(raw)

        if source == "database":
            from merakisync.database import get_engine
            engine = get_engine()
            where: list[str] = ["network_id = :network_id"]
            params: dict = {"network_id": network_id}

            if ts and ts != "all":
                where += ["active_from <= :ts", "(active_to > :ts OR active_to IS NULL)"]
                params["ts"] = ts
            elif ts != "all":
                where.append("active_to IS NULL")

            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)} LIMIT 1"
            )
            with engine.connect() as conn:
                row = conn.execute(sql, params).mappings().fetchone()
            return cls.from_row(row) if row else None

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], network_id: str) -> I | None:
        """Fetch the DHCP server policy for *network_id* and upsert into the database."""
        policy = cls.get(network_id, source="meraki")
        if not policy:
            logger.warning("No DHCP server policy returned for network %s.", network_id)
            return None

        policy.upsert()
        logger.debug("DhcpServerPolicy synced for network %s.", network_id)
        return policy
