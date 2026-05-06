from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="Vlan")


@dataclass()
class Vlan(MerakiObj):
    """Meraki MX appliance VLAN — maps to meraki.vlan.

    Retrieved via GET /networks/{networkId}/appliance/vlans.
    network_id is injected into the raw dict before calling from_dashboard().

    Note: GET /organizations/{organizationId}/appliance/vlans is not yet
    available in the Meraki Python SDK (v3.0.1). sync() uses the per-network
    endpoint and is called inside the appliance-network loop in cmd_sync.py.

    PK: (network_id, vlan_id)
    """

    __table_name__: ClassVar[str] = "vlan"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id", "vlan_id")
    __mapping_override__: ClassVar[dict[str, str]] = {
        "vlan_id": "id",   # "id" conflicts with Python builtin
    }

    # PK fields — required
    network_id: str
    vlan_id: int

    # Required fields
    name: str

    # Optional fields
    appliance_ip: str | None = None
    subnet: str | None = None
    interface_id: str | None = None
    group_policy_id: str | None = None
    template_vlan_type: str | None = None
    cidr: str | None = None
    mask: int | None = None
    dhcp_handling: str | None = None
    dhcp_lease_time: str | None = None
    dhcp_boot_options_enabled: bool | None = None
    dhcp_boot_next_server: str | None = None
    dhcp_boot_filename: str | None = None
    dns_nameservers: str | None = None
    vpn_nat_subnet: str | None = None
    dhcp_relay_server_ips: list | None = None
    fixed_ip_assignments: dict | None = None
    reserved_ip_ranges: list | None = None
    dhcp_options: list | None = None
    mandatory_dhcp: dict | None = None
    ipv6: dict | None = None

    # SCD2 versioning
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    # ------------------------------------------------------------------
    # Resource path
    # ------------------------------------------------------------------

    @property
    def resource_path(self) -> str:
        """Meraki API path for this VLAN. GET /networks/{networkId}/appliance/vlans/{vlanId}"""
        return f"/networks/{self.network_id}/appliance/vlans/{self.vlan_id}"

    # ------------------------------------------------------------------
    # from_dashboard override
    # ------------------------------------------------------------------

    @classmethod
    def from_dashboard(cls: Type[I], data: dict[str, Any]) -> I:
        """Map a Meraki API dict to a Vlan instance.

        Coerces `id` to int before delegating to the base class, since the
        Meraki API returns VLAN IDs as strings.
        """
        flat = dict(data)
        if "id" in flat:
            flat["id"] = int(flat["id"])
        return super().from_dashboard(flat)

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
        vlan_id: int | None = None,
        name: str | None = None,
    ) -> list[I]:
        """Retrieve VLANs for a network.

        Args:
            network_id: Meraki network ID.
            source:     "meraki" or "database".
            ts:         Timestamp filter (DB only).
            vlan_id:    Filter by VLAN ID.
            name:       ILIKE name filter (DB only) or exact match (Meraki).
        """
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            raw_vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
            vlans: list[I] = []
            for raw in raw_vlans:
                flat = dict(raw)
                flat["networkId"] = network_id
                vlan = cls.from_dashboard(flat)
                if vlan_id is not None and vlan.vlan_id != vlan_id:
                    continue
                if name and vlan.name != name:
                    continue
                vlans.append(vlan)
            return vlans

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

            if vlan_id is not None:
                where.append("vlan_id = :vlan_id")
                params["vlan_id"] = vlan_id
            if name:
                where.append("name ILIKE :name")
                params["name"] = f"%{name}%"

            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)}"
                " ORDER BY vlan_id"
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
        """Fetch all VLANs for *network_id* from Meraki and upsert into the database.

        Networks with VLANs disabled return a 400 from the API — these are
        skipped silently since it is a normal configuration state, not an error.
        """
        from meraki.exceptions import APIError
        try:
            vlans = cls.get(network_id, source="meraki")
        except APIError as exc:
            if exc.status == 400 and "VLANs are not enabled" in str(exc):
                logger.debug("VLANs not enabled for network %s — skipping.", network_id)
                return []
            raise
        if not vlans:
            logger.debug("No VLANs returned for network %s.", network_id)
            return []
        counts = cls.upsert_many(vlans)
        logger.info("VLANs synced for network %s: %s", network_id, counts)
        return vlans
