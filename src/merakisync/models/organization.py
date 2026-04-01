from dataclasses import dataclass
from typing import ClassVar, Literal, TypeVar, Type
from meraki_sync.models.base import MerakiObj
from meraki_sync import get_dashboard, get_engine
from datetime import datetime
from sqlalchemy import text

I = TypeVar("I", bound="Organization")

@dataclass(frozen=True, slots=True)
class Organization(MerakiObj):
    __table_name__ = "organization"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    id: str
    name: str
    url: str
    api: dict
    licensing: dict
    cloud: dict
    management: dict


    @classmethod
    def get(cls: Type[I],
            source: Literal["database", "meraki"] = "database",
            name: str = "",
            ts: datetime | Literal["all"] | None = None
            ) -> list[I] | None:
        """Retrieves all organizations"""
        
        name = name.strip().lower()
        if ts and source == "meraki":
            raise ValueError("Cannot perform timestamped lookups when source is Meraki. Use source database instead.")


        if source == "meraki":
            organizations = []
            dashboard = get_dashboard()
            results = dashboard.organizations.getOrganizations()
            for row in results:
                org = cls.from_dashboard(row)
                if name and org.name.strip().lower() != name:
                    continue
                organizations.append(org)
            return organizations


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

            where_sql = " AND ".join(where) if where else "TRUE"

            sql = text(f"""
                SELECT *
                FROM {cls.__schema__}.{cls.__table_name__}
                WHERE {where_sql}
            """)

            with engine.connect() as conn:
                results = conn.execute(sql, params).mappings().all()
                return [cls.from_row(row) for row in results]

        else:
            raise ValueError(f"Invalid source '{source}'. Must be one of: ['database', 'meraki']")


    @classmethod
    def sync(cls):
        """Syncs all organizations from Meraki into the database"""
        orgs = cls.get(source="meraki")
        if not orgs:
            return "Failed to retrieve orgs from Meraki"

        for org in orgs:
            org.upsert()
