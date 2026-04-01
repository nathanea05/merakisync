from dataclasses import dataclass
from typing import ClassVar, Literal, TypeVar, Type
from merakisync.models.base import MerakiObj
from merakisync import get_dashboard, get_engine
from datetime import datetime
from sqlalchemy import text

I = TypeVar("I", bound="xyz")

@dataclass(frozen=True, slots=True)
class xyz(MerakiObj):
    __table_name__ = ""
    __pk__ = ("id",)
    __mapping_override__ = {}

    id: str


    @classmethod
    def get(cls: Type[I],
            source: Literal["database", "meraki"] = "database",
            ts: datetime | Literal["all"] | None = None
            ) -> list[I] | None:

        if ts and source == "meraki":
            raise ValueError("Cannot perform timestamped lookups when source is Meraki. Use source database instead.")

        if source == "meraki":
            dashboard = get_dashboard()


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
        results = cls.get(source="meraki")
        if not results:
            return "Failed to retrieve data from Meraki"

        for row in results:
            row.upsert()

        return f"Synced {len(results)} items from Meraki"
