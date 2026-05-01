from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="L3FirewallRule")


@dataclass(frozen=True, slots=True)
class L3FirewallRule(MerakiObj):
    """Meraki MX L3 firewall rule — maps to meraki.l3_firewall_rule.

    Retrieved via GET /networks/{networkId}/appliance/firewall/l3FirewallRules.

    The API returns an ordered list of rules.  Rules have no stable identifier
    of their own — their position in the list is their identity.  PK is
    (network_id, rule_order) where rule_order is the 0-based index.

    SCD2 notes:
    - When any rule at a given position changes, the old row is expired and a
      new row is inserted.  If rules are reordered, multiple rows are affected.
    - The sync() method compares the full current rule set and only performs
      writes for positions that actually changed, which keeps the change
      footprint small for large rule sets.
    - Meraki always appends a final "default rule" (allow any/any) at the
      bottom; this is included in the sync as a normal row.
    """

    __table_name__: ClassVar[str] = "l3_firewall_rule"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id", "rule_order")
    __mapping_override__: ClassVar[dict[str, str]] = {
        "network_id": "networkId",
        "rule_order": "ruleOrder",
        "dest_port": "destPort",
        "dest_cidr": "destCidr",
        "src_port": "srcPort",
        "src_cidr": "srcCidr",
        "syslog_enabled": "syslogEnabled",
    }

    # Business fields
    network_id: str        # injected
    rule_order: int        # injected (0-based index in rules array)
    comment: str | None = None
    policy: str | None = None       # "allow" | "deny"
    protocol: str | None = None     # "tcp" | "udp" | "icmp" | "icmp6" | "any"
    dest_port: str | None = None
    dest_cidr: str | None = None
    src_port: str | None = None
    src_cidr: str | None = None
    syslog_enabled: bool | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Closest Meraki API path for this firewall rule's parent collection.

        The Meraki API has no per-rule endpoint. Rules are only accessible
        as an ordered list for the whole network. To read or update rules,
        use the collection endpoint below and filter by rule_order client-side.
        GET /networks/{networkId}/appliance/firewall/l3FirewallRules
        """
        return f"/networks/{self.network_id}/appliance/firewall/l3FirewallRules"

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
        policy: str | None = None,
        protocol: str | None = None,
    ) -> list[I]:
        """Retrieve L3 firewall rules for a network, ordered by rule_order.

        Args:
            network_id: Meraki network ID.
            source:     "meraki" or "database".
            ts:         Timestamp filter (DB only).
            policy:     Filter by policy — "allow" or "deny" (DB only).
            protocol:   Filter by protocol (DB only).
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            response = dashboard.appliance.getNetworkApplianceFirewallL3FirewallRules(network_id)
            rules_raw: list[dict[str, Any]] = response.get("rules", [])

            rules: list[I] = []
            for order, raw in enumerate(rules_raw):
                flat = dict(raw)
                flat["networkId"] = network_id
                flat["ruleOrder"] = order
                rules.append(cls.from_dashboard(flat))
            return rules

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

            if policy:
                where.append("policy = :policy")
                params["policy"] = policy
            if protocol:
                where.append("protocol = :protocol")
                params["protocol"] = protocol

            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)}"
                " ORDER BY rule_order"
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
        """Fetch L3 firewall rules for *network_id* from Meraki and upsert.

        Operates on each rule position independently so only changed
        positions generate database writes.
        """
        rules = cls.get(network_id, source="meraki")
        if not rules:
            logger.debug("No L3 firewall rules returned for network %s.", network_id)
            return []

        counts = cls.upsert_many(rules)
        logger.debug("L3FirewallRules synced for network %s: %s", network_id, counts)
        return rules
