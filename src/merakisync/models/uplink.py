from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Uplink")


@dataclass()
class Uplink(MerakiObj):
    """Meraki MX/Z uplink status — maps to meraki.uplink.

    The Meraki API returns uplinks nested under a per-device response from
    getOrganizationUplinksStatuses.  The sync method flattens this structure
    before calling from_dashboard().
    """

    __table_name__: ClassVar[str] = "uplink"
    __pk__: ClassVar[tuple[str, ...]] = ("serial", "interface")
    __mapping_override__: ClassVar[dict[str, str]] = {
        # Correct spelling — API returns "ipAssignedBy"
        "ip_assigned_by": "ipAssignedBy",
    }

    # Business fields
    serial: str
    interface: str
    network_id: str | None = None
    status: str | None = None
    ip: str | None = None
    gateway: str | None = None
    public_ip: str | None = None
    primary_dns: str | None = None
    secondary_dns: str | None = None
    ip_assigned_by: str | None = None
    signal_stat: dict | None = None
    connection_type: str | None = None
    apn: str | None = None
    dns1: str | None = None
    dns2: str | None = None
    signal_type: str | None = None
    mtu: int | None = None
    iccid: str | None = None
    imsi: str | None = None
    msisdn: str | None = None
    mcc: str | None = None
    mnc: str | None = None
    roaming: dict | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Closest Meraki API path for this uplink's parent device.

        The Meraki API has no per-uplink GET endpoint. Uplink statuses are
        only available at the organization level via
        GET /organizations/{organizationId}/uplinks/statuses, which is not
        navigable from this object (org_id is not stored). The device path
        is the most specific navigable path available.
        """
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
        network_id: str | None = None,
        serial: str | None = None,
        interface: str | None = None,
        status: str | None = None,
        ip_assigned_by: str | None = None,
    ) -> list[I]:
        """Retrieve uplink statuses for an organization.

        Args:
            org_id:         Meraki organization ID.
            source:         "meraki" or "database".
            ts:             Timestamp filter (DB only).
            network_id:     Filter by network ID.
            serial:         Filter by device serial.
            interface:      Filter by uplink interface name (e.g. "wan1").
            status:         Filter by uplink status (e.g. "active").
            ip_assigned_by: Filter by IP assignment method.
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()

            api_kwargs: dict = {"total_pages": "all"}
            if network_id:
                api_kwargs["networkIds"] = [network_id]
            if serial:
                api_kwargs["serials"] = [serial]

            response = dashboard.organizations.getOrganizationUplinksStatuses(
                org_id, **api_kwargs
            )

            uplinks: list[I] = []
            for device_data in response:
                net_id = device_data.get("networkId")
                dev_serial = device_data.get("serial")
                for raw in device_data.get("uplinks", []):
                    flat = dict(raw)
                    flat["networkId"] = net_id
                    flat["serial"] = dev_serial
                    uplinks.append(cls.from_dashboard(flat))

            # Client-side filters not supported by the API
            if interface:
                uplinks = [u for u in uplinks if u.interface == interface]
            if status:
                uplinks = [u for u in uplinks if u.status == status]
            if ip_assigned_by:
                uplinks = [u for u in uplinks if u.ip_assigned_by == ip_assigned_by]

            return uplinks

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
            if interface:
                where.append("interface = :interface")
                params["interface"] = interface
            if status:
                where.append("status = :status")
                params["status"] = status
            if ip_assigned_by:
                where.append("ip_assigned_by = :ip_assigned_by")
                params["ip_assigned_by"] = ip_assigned_by

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
        """Fetch uplink statuses for *org_id* from Meraki and upsert into the database."""
        uplinks = cls.get(org_id, source="meraki")
        if not uplinks:
            logger.warning("No uplinks returned for org %s.", org_id)
            return []

        counts = cls.upsert_many(uplinks)
        logger.info("Uplinks synced for org %s: %s", org_id, counts)
        return uplinks
