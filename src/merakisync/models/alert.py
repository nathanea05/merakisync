from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Alert")


@dataclass()
class Alert(MerakiObj):
    """Meraki Assurance Alert — maps to meraki.alert.

    Retrieved via GET /organizations/{organizationId}/assurance/alerts.

    The API response embeds the network as a nested object
    {"id": "...", "name": "..."}.  from_dashboard() cannot handle nested
    objects automatically, so Alert provides its own from_dashboard() that
    flattens network.id → network_id and network.name → network_name before
    delegating to the parent.

    Alerts can transition states (startedAt → resolvedAt → dismissedAt), so
    SCD2 versioning is used to track those changes.
    """

    __schema__: ClassVar[str] = "meraki"
    __table_name__: ClassVar[str] = "alert"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    # "type" is a Python builtin — map it to alert_type
    __mapping_override__: ClassVar[dict[str, str]] = {
        "alert_type": "type",
    }

    # Business fields
    id: str
    org_id: str               # injected during sync
    category_type: str | None = None
    network_id: str | None = None    # flattened from network.id
    network_name: str | None = None  # flattened from network.name
    started_at: str | None = None
    resolved_at: str | None = None
    dismissed_at: str | None = None
    device_type: str | None = None
    alert_type: str | None = None
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    scope: dict | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Custom from_dashboard — flatten nested network object
    # ------------------------------------------------------------------

    @classmethod
    def from_dashboard(cls: Type[I], data: dict[str, Any]) -> I:  # type: ignore[override]
        """Extend the base converter to flatten the nested 'network' object."""
        flat = dict(data)

        network = flat.pop("network", None)
        if isinstance(network, dict):
            flat.setdefault("network_id", network.get("id"))
            flat.setdefault("network_name", network.get("name"))

        return super().from_dashboard(flat)

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this alert. GET /organizations/{orgId}/assurance/alerts/{id}"""
        return f"/organizations/{self.org_id}/assurance/alerts/{self.id}"

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
        alert_id: str | None = None,
        network_id: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        active_only: bool = False,
    ) -> list[I]:
        """Retrieve alerts for an organization.

        Args:
            org_id:      Meraki organization ID.
            source:      "meraki" or "database".
            ts:          Timestamp filter (DB only).
            alert_id:    Filter by alert ID.
            network_id:  Filter by network ID.
            severity:    Filter by severity level.
            alert_type:  Filter by alert type string.
            active_only: When source='meraki', pass active=True to the API to
                         retrieve only currently-active (unresolved) alerts.
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()

            api_kwargs: dict = {"total_pages": "all"}
            if active_only:
                api_kwargs["active"] = True
            if network_id:
                api_kwargs["networkId"] = network_id
            if severity:
                api_kwargs["severity"] = severity
            if alert_type:
                api_kwargs["types"] = [alert_type]

            raw_alerts = dashboard.organizations.getOrganizationAssuranceAlerts(
                org_id, **api_kwargs
            )

            alerts: list[I] = []
            for raw in raw_alerts:
                flat = dict(raw)
                flat["orgId"] = org_id
                alert = cls.from_dashboard(flat)
                if alert_id and alert.id != alert_id:
                    continue
                alerts.append(alert)
            return alerts

        if source == "database":
            from merakisync.database import get_engine
            engine = get_engine()
            where: list[str] = ["org_id = :org_id"]
            params: dict = {"org_id": org_id}

            if ts and ts != "all":
                where += ["active_from <= :ts", "(active_to > :ts OR active_to IS NULL)"]
                params["ts"] = ts
            elif ts != "all":
                where.append("active_to IS NULL")

            if alert_id:
                where.append("id = :alert_id")
                params["alert_id"] = alert_id
            if network_id:
                where.append("network_id = :network_id")
                params["network_id"] = network_id
            if severity:
                where.append("severity = :severity")
                params["severity"] = severity
            if alert_type:
                where.append("alert_type = :alert_type")
                params["alert_type"] = alert_type

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
        """Fetch alerts for *org_id* from Meraki and upsert into the database."""
        alerts = cls.get(org_id, source="meraki", active_only=False)
        if not alerts:
            logger.info("No alerts returned for org %s.", org_id)
            return []

        counts = cls.upsert_many(alerts)
        logger.info("Alerts synced for org %s: %s", org_id, counts)
        return alerts
