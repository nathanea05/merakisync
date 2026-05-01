from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="UplinkUsage")


@dataclass(frozen=True, slots=True)
class UplinkUsage(MerakiObj):
    """Meraki MX/Z uplink bandwidth usage, tracked per calendar month.

    Maps to meraki.uplink_usage.

    Retrieved via GET /organizations/{organizationId}/appliance/uplinks/usage/byNetwork.

    Design notes:
    - PK: (network_id, serial, interface, month, year).  Each record stores the
      cumulative bytes for that uplink interface for the given month as of the
      last sync.  On each sync run the existing record is overwritten with the
      latest cumulative total — SCD2 versioning is not appropriate here because
      this is a rolling metric, not a configuration state.
    - The Meraki API supports a maximum lookback of 30 days when using t0/t1.
      For months that began more than 30 days ago the first few days will not
      be accessible via the API; only the current and recent months should be
      considered reliable.
    - __versioned__ = False causes the base class to use a simple
      INSERT … ON CONFLICT DO UPDATE instead of SCD2 logic.
    """

    __table_name__: ClassVar[str] = "uplink_usage"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id", "serial", "interface", "month", "year")
    __mapping_override__: ClassVar[dict[str, str]] = {}
    __versioned__: ClassVar[bool] = False   # simple UPSERT, not SCD2

    # Business fields
    network_id: str
    serial: str
    interface: str
    month: int
    year: int
    sent: int | None = None
    received: int | None = None

    # No active_from / active_to; only last_seen to record when we last synced
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Closest Meraki API path for this uplink usage record.

        The Meraki API has no per-record endpoint for uplink usage. The
        network-level endpoint below returns time-series usage for all
        uplinks in the network; filter by serial and interface client-side.
        GET /networks/{networkId}/appliance/uplinks/usageHistory
        """
        return f"/networks/{self.network_id}/appliance/uplinks/usageHistory"

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    @classmethod
    def get(
        cls: Type[I],
        org_id: str,
        source: Literal["database", "meraki"] = "database",
        *,
        month: int | None = None,
        year: int | None = None,
        network_id: str | None = None,
        serial: str | None = None,
        interface: str | None = None,
    ) -> list[I]:
        """Retrieve uplink usage records.

        For source='meraki', month and year default to the current calendar
        month.  The API is queried from the first second of that month to the
        current time (capped at the 30-day API lookback window).

        Args:
            org_id:     Meraki organization ID.
            source:     "meraki" or "database".
            month:      Calendar month (1-12).  Defaults to current month.
            year:       Calendar year.  Defaults to current year.
            network_id: Optional network ID filter.
            serial:     Optional device serial filter.
            interface:  Optional interface name filter (e.g. "wan1").
        """
        now = datetime.now(tz=timezone.utc)
        month = month or now.month
        year = year or now.year

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()

            month_start = datetime(year, month, 1, tzinfo=timezone.utc)
            # Clamp t0 to 30-day lookback limit
            lookback_limit = now.replace(
                hour=now.hour, minute=now.minute, second=now.second, microsecond=0
            )
            from datetime import timedelta
            thirty_days_ago = now - timedelta(days=30)
            t0 = max(month_start, thirty_days_ago)
            t1 = now

            response = dashboard.organizations.getOrganizationApplianceUplinksUsageByNetwork(
                org_id,
                t0=t0.isoformat(),
                t1=t1.isoformat(),
            )

            usages: list[I] = []
            for net_data in response:
                net_id = net_data.get("networkId", "")
                if network_id and net_id != network_id:
                    continue
                for uplink_data in net_data.get("byUplink", []):
                    dev_serial = uplink_data.get("serial", "")
                    iface = uplink_data.get("interface", "")
                    if serial and dev_serial != serial:
                        continue
                    if interface and iface != interface:
                        continue
                    usages.append(
                        cls(
                            network_id=net_id,
                            serial=dev_serial,
                            interface=iface,
                            month=month,
                            year=year,
                            sent=uplink_data.get("sent"),
                            received=uplink_data.get("received"),
                        )
                    )
            return usages

        if source == "database":
            from merakisync.database import get_engine
            engine = get_engine()
            where: list[str] = ["month = :month", "year = :year"]
            params: dict = {"month": month, "year": year}

            if network_id:
                where.append("network_id = :network_id")
                params["network_id"] = network_id
            if serial:
                where.append("serial = :serial")
                params["serial"] = serial
            if interface:
                where.append("interface = :interface")
                params["interface"] = interface

            sql = text(f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)}")
            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @classmethod
    def sync(cls: Type[I], org_id: str) -> list[I]:
        """Fetch current-month uplink usage for *org_id* and upsert into the database.

        Existing records for the current month are updated with the latest
        cumulative byte counts.  Records for previous months are never modified.
        """
        usages = cls.get(org_id, source="meraki")
        if not usages:
            logger.warning("No uplink usage returned for org %s.", org_id)
            return []

        counts = cls.upsert_many(usages)
        logger.info("UplinkUsage synced for org %s: %s", org_id, counts)
        return usages
