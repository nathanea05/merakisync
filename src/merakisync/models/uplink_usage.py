from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="UplinkUsage")


@dataclass()
class UplinkUsage(MerakiObj):
    """Meraki MX/Z uplink bandwidth usage, tracked per calendar month.

    Maps to meraki.uplink_usage.

    Retrieved via GET /organizations/{organizationId}/appliance/uplinks/usage/byNetwork.

    Design notes:
    - PK: (network_id, serial, interface, month, year).  Each record stores the
      true cumulative bytes for that uplink for the full month to date.
    - sync() uses an incremental window: it reads last_seen from the DB as t0
      and queries only the delta since the last sync, then accumulates those
      bytes onto the existing stored total.  This produces accurate monthly
      totals provided syncs run at least every 14 days (the API's max window).
    - last_seen records the end of the last successfully synced window (t1),
      not the wall-clock time of the sync run.  The next sync uses it as t0.
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

            from datetime import timedelta
            month_start = datetime(year, month, 1, tzinfo=timezone.utc)
            # t0 lookback limit: 30 days. t1 limit: t0 + 14 days (API constraint).
            t0 = max(month_start, now - timedelta(days=30))
            t1 = min(now, t0 + timedelta(days=14))

            response = dashboard.appliance.getOrganizationApplianceUplinksUsageByNetwork(
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

        Uses an incremental window strategy to build accurate monthly totals:

        1. Load existing records for the current month from the DB.
        2. Use the most recent last_seen as t0 (falling back to month start on the
           first sync of the month).
        3. Query the API for bytes in the t0→now window only.
        4. Accumulate the delta bytes on top of the existing stored totals.
        5. Upsert with last_seen=t1 so the next sync continues from where this
           one ended.

        Each sync covers at most a 14-day window (the API's per-query maximum).
        Gaps up to 30 days can be fully recovered across multiple syncs. If more
        than 30 days pass between syncs, data older than the 30-day lookback limit
        is unrecoverable and a warning is logged.
        """
        from datetime import timedelta
        from merakisync.dashboard import get_dashboard

        now = datetime.now(tz=timezone.utc)
        month = now.month
        year = now.year
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)

        # --- Step 1: load existing records for this month --------------------
        existing = cls.get(org_id, source="database", month=month, year=year)
        existing_map: dict[tuple[str, str, str], I] = {
            (r.network_id, r.serial, r.interface): r for r in existing
        }

        # --- Step 2: compute t0 from last_seen -------------------------------
        last_seen_values = [r.last_seen for r in existing if r.last_seen is not None]
        if last_seen_values:
            t0 = max(last_seen_values)
            gap = now - t0
            # Clamp to the API's 30-day absolute lookback limit.
            t0_clamped = max(t0, now - timedelta(days=30))
            if t0_clamped > t0:
                # Gap exceeds the API's lookback window — data before t0_clamped
                # cannot be recovered.
                logger.warning(
                    "Uplink usage gap for org %s: last sync was %d days ago. "
                    "Data from %s to %s is unrecoverable (API 30-day lookback limit).",
                    org_id, gap.days,
                    t0.strftime("%Y-%m-%d"),
                    t0_clamped.strftime("%Y-%m-%d"),
                )
            t0 = t0_clamped
        else:
            t0 = month_start

        t1 = min(now, t0 + timedelta(days=14))

        # --- Step 3: query API for the delta window --------------------------
        dashboard = get_dashboard()
        response = dashboard.appliance.getOrganizationApplianceUplinksUsageByNetwork(
            org_id,
            t0=t0.isoformat(),
            t1=t1.isoformat(),
        )

        # --- Step 4: accumulate delta bytes onto existing totals -------------
        accumulated: list[I] = []
        for net_data in response:
            net_id = net_data.get("networkId", "")
            for uplink_data in net_data.get("byUplink", []):
                dev_serial = uplink_data.get("serial", "")
                iface = uplink_data.get("interface", "")
                delta_sent = uplink_data.get("sent") or 0
                delta_received = uplink_data.get("received") or 0

                prior = existing_map.get((net_id, dev_serial, iface))
                new_sent = (prior.sent or 0) + delta_sent if prior else delta_sent
                new_received = (prior.received or 0) + delta_received if prior else delta_received

                accumulated.append(cls(
                    network_id=net_id,
                    serial=dev_serial,
                    interface=iface,
                    month=month,
                    year=year,
                    sent=new_sent,
                    received=new_received,
                    last_seen=t1,   # written to DB; used as t0 on the next sync
                ))

        if not accumulated:
            logger.warning("No uplink usage returned for org %s.", org_id)
            return []

        counts = cls.upsert_many(accumulated)
        logger.info("UplinkUsage synced for org %s: %s", org_id, counts)
        return accumulated
