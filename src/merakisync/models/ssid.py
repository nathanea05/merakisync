from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Ssid")


@dataclass()
class Ssid(MerakiObj):
    """Meraki wireless SSID — maps to meraki.ssid.

    Retrieved via GET /networks/{networkId}/wireless/ssids.
    network_id is injected before calling from_dashboard().

    PK: (network_id, number)
    """

    __table_name__: ClassVar[str] = "ssid"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id", "number")
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # PK fields — required
    network_id: str
    number: int

    # Optional fields
    name: str | None = None
    enabled: bool | None = None
    splash_page: str | None = None
    ssid_admin_accessible: bool | None = None
    local_auth: bool | None = None
    auth_mode: str | None = None
    psk: str | None = None
    encryption_mode: str | None = None
    wpa_encryption_mode: str | None = None
    radius_servers: list | None = None
    radius_accounting_servers: list | None = None
    radius_accounting_enabled: bool | None = None
    radius_enabled: bool | None = None
    radius_attribute_for_group_policies: str | None = None
    radius_failover_policy: str | None = None
    radius_load_balancing_policy: str | None = None
    ip_assignment_mode: str | None = None
    admin_splash_url: str | None = None
    splash_timeout: str | None = None
    walled_garden_enabled: bool | None = None
    walled_garden_ranges: list | None = None
    min_bitrate: int | None = None
    band_selection: str | None = None
    per_client_bandwidth_limit_up: int | None = None
    per_client_bandwidth_limit_down: int | None = None
    visible: bool | None = None
    available_on_all_aps: bool | None = None
    availability_tags: list | None = None
    per_ssid_bandwidth_limit_up: int | None = None
    per_ssid_bandwidth_limit_down: int | None = None
    mandatory_dhcp_enabled: bool | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this SSID. GET /networks/{networkId}/wireless/ssids/{number}"""
        return f"/networks/{self.network_id}/wireless/ssids/{self.number}"

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
        number: int | None = None,
        enabled: bool | None = None,
    ) -> list[I]:
        """Retrieve SSIDs for a network.

        Args:
            network_id: Meraki network ID.
            source:     "meraki" or "database".
            ts:         Timestamp filter (DB only).
            number:     Filter by SSID number (0–14).
            enabled:    Filter by enabled state (DB only).
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            raw_ssids = dashboard.wireless.getNetworkWirelessSsids(network_id)
            ssids: list[I] = []
            for raw in raw_ssids:
                flat = dict(raw)
                flat["networkId"] = network_id
                ssid = cls.from_dashboard(flat)
                if number is not None and ssid.number != number:
                    continue
                ssids.append(ssid)
            return ssids

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

            if number is not None:
                where.append("number = :number")
                params["number"] = number
            if enabled is not None:
                where.append("enabled = :enabled")
                params["enabled"] = enabled

            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)}"
                " ORDER BY number"
            )
            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], network_id: str) -> list[I]:
        """Fetch all SSIDs for *network_id* from Meraki and upsert into the database."""
        ssids = cls.get(network_id, source="meraki")
        if not ssids:
            logger.debug("No SSIDs returned for network %s.", network_id)
            return []
        counts = cls.upsert_many(ssids)
        logger.debug("SSIDs synced for network %s: %s", network_id, counts)
        return ssids
