from dataclasses import dataclass
from typing import ClassVar, Literal, TypeVar, Type
from merakisync.models.base import MerakiObj
from merakisync import get_dashboard, get_engine
from datetime import datetime
from sqlalchemy import text

I = TypeVar("I", bound="DhcpServerPolicy")

@dataclass(frozen=True, slots=True)
class DhcpServerPolicy(MerakiObj):
    __table_name__ = "dhcp_server_policy"
    __pk__ = ("network_id",)
    __mapping_override__ = {}

    network_id: str # Injected
    default_policy: str
    blocked_servers: list[str]
    allowed_servers: list[str]
    always_allowed_servers: list[str]
    arp_inspection: dict

    @classmethod
    def get(cls: Type[I],
            network_id: str,
            source: Literal["database", "meraki"] = "database",
            ts: datetime | Literal["all"] | None = None,
            ) -> I | None:

        if ts and source == "meraki":
            raise ValueError("Cannot perform timestamped lookups when source is Meraki. Use source database instead.")

        if source == "meraki":
            dashboard = get_dashboard()
            raw_dhcp_server_policy = dashboard.switch.getNetworkSwitchDhcpServerPolicy(network_id)
            raw_dhcp_server_policy["networkId"] = network_id
            dhcp_server_policy = cls.from_dashboard(raw_dhcp_server_policy)
            return dhcp_server_policy


        elif source == "database":
            engine = get_engine()

            where = []
            params = {}

            if ts and ts != "all":
                where.append("active_from <= :ts")
                where.append("(active_to > :ts OR active_to IS NULL)")
                params["ts"] = ts
            elif ts != "all":
                where.append("active_to IS NULL")

            if network_id:
                where.append("network_id = :network_id")
                params["network_id"] = network_id

            where_sql = " AND ".join(where) if where else "TRUE"

            sql = text(f"""
                SELECT *
                FROM {cls.__schema__}.{cls.__table_name__}
                WHERE {where_sql}
            """)

            with engine.connect() as conn:
                result = conn.execute(sql, params).mappings().fetchone()
                if not result:
                    return None

                return cls.from_row(result)

        else:
            raise ValueError(f"Invalid source '{source}'. Must be one of: ['database', 'meraki']")

    
    @classmethod
    def sync(cls, network_id):
        result = cls.get(source="meraki", network_id=network_id)
        if not result:
            return "Failed to retrieve data from Meraki"

        return f"Synced DHCP Server Policy from Meraki"
