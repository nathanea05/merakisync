from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeVar, Type

from sqlalchemy import text

from merakisync import get_dashboard, get_engine
from merakisync.models.base import MerakiObj
from merakisync.utils.filter_array import filter_array

I = TypeVar("I", bound="Network")

@dataclass(frozen=True, slots=True)
class Network(MerakiObj):
    __table_name__ = "network"
    __pk__ = ("id",)
    __mapping_override__ = {}

    id: str
    organization_id: str
    name: str
    product_types: list
    time_zone: str
    tags: list
    enrollment_string: str
    url: str
    notes: str
    is_bound_to_config_template: bool


    @classmethod
    def get(cls: Type[I],
            org_id: str,
            source: Literal["database", "meraki"] = "database",
            ts: datetime | Literal["all"] | None = None,

            name: str = "",
            network_id: str = "",
            tags_include: list[str] = [],
            tags_exclude: list[str] = [],
            product_types_include: list[str] = [],
            product_types_exclude: list[str] = []
            ) -> list[I] | None:

        if ts and source == "meraki":
            raise ValueError("Cannot perform timestamped lookups when source is Meraki. Use source database instead.")

        if source == "meraki":
            filtered_networks = []
            dashboard = get_dashboard()
            raw_networks = dashboard.organizations.getOrganizationNetworks(org_id, total_pages="all")
            networks = [cls.from_dashboard(raw_network) for raw_network in raw_networks]

            for network in networks:
                if name and network.name != name:
                    continue
                if network_id and network.id != network_id:
                    continue
                if not filter_array(
                        values = set(network.tags),
                        include = tags_include,
                        exclude = tags_exclude
                        ):
                    continue
                if not filter_array(
                        values = set(network.product_types),
                        include = product_types_include,
                        exclude = product_types_exclude
                        ):
                    continue

                
                filtered_networks.append(network)

            filtered_networks.sort(key=lambda network: network.name)

            return filtered_networks


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

            if name:
                where.append("name ILIKE :name")
                params["name"] = name

            if network_id:
                where.append("id ILIKE :network_id")
                params["network_id"] = network_id

            if tags_include:
                where.append("tags ?& :tags_include")
                params["tags_include"] = tags_include

            if tags_exclude:
                where.append("NOT (tags ?| :tags_exclude)")
                params["tags_exclude"] = tags_exclude



            where_sql = " AND ".join(where) if where else "TRUE"

            sql = text(f"""
                SELECT *
                FROM {cls.__schema__}.{cls.__table_name__}
                WHERE {where_sql}
            """)

            with engine.connect() as conn:
                results = conn.execute(sql, params).mappings().all()
                networks = [cls.from_row(row) for row in results]
                networks.sort(key=lambda network: network.name)
                return networks
            

        else:
            raise ValueError(f"Invalid source '{source}'. Must be one of: ['database', 'meraki']")

    
    @classmethod
    def sync(cls: Type[I], org_id: str) -> list[I] | None:
        results = cls.get(source="meraki", org_id=org_id)
        if not results:
            return None

        for row in results:
            row.upsert()

        return results
