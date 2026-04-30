from dataclasses import dataclass
from typing import ClassVar, Literal, TypeVar, Type

from sqlalchemy.event import api
from merakisync.models.base import MerakiObj
from merakisync import get_dashboard, get_engine
from merakisync.utils import filter_array
from datetime import datetime
from sqlalchemy import text

I = TypeVar("I", bound="Device")

@dataclass(frozen=True, slots=True)
class Device(MerakiObj):
    __table_name__ = "device"
    __pk__ = ("serial",)
    __mapping_override__ = {}

    serial: str
    name: str | None = None
    network_id: str | None = None
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    model: str | None = None
    mac: str | None = None
    lan_ip: str | None = None
    firmware: str | None = None
    floor_plan_id: str | None = None
    details: list[dict] | None = None
    beacon_id_params: dict | None = None
    status: str | None = None


    @classmethod
    def get(cls: Type[I],
            org_id: str,
            source: Literal["database", "meraki"] = "database",
            ts: datetime | Literal["all"] | None = None,

            serial: str = "",
            name: str = "",
            network_id: str = "",
            tags_include: list[str] = [],
            tags_exclude: list[str] = [],
            status: str = "",
            model: str = "",

            product_types_include: list[Literal["appliance", "switch", "wireless"]] = [],
            product_types_exclude: list[Literal["appliance", "switch", "wireless"]] = [],
            ) -> list[I] | None:

        if ts and source == "meraki":
            raise ValueError("Cannot perform timestamped lookups when source is Meraki. Use source database instead.")

        if source == "meraki":
            filtered_devices = []
            dashboard = get_dashboard()

            api_kwargs: dict = {
                    "organizationId": org_id,
                    "total_pages": "all",
                    }


            if serial:
                api_kwargs["serial"] = serial

            if network_id:
                api_kwargs["networkIds"] = [network_id]

            if product_types_include:
                api_kwargs["productTypes"] = product_types_include

            if tags_include:
                api_kwargs["tags"] = tags_include

            if name:
                api_kwargs["name"] = name

            if model:
                api_kwargs["model"] = model

            raw_devices = dashboard.organizations.getOrganizationDevices(**api_kwargs)

            devices = [cls.from_dashboard(raw_device) for raw_device in raw_devices]


            # Filters not supported by Meraki Dashboard
            for device in devices:
                # Filter excluded tags
                if not filter_array(
                        values = set(device.tags),
                        include = tags_include,
                        exclude = tags_exclude
                        ):
                    continue

                if status and device.status != status:
                    continue

                filtered_devices.append(device)

            return filtered_devices


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

            if serial:
                where.append("serial = :serial")
                params["serial"] = serial

            if network_id:
                where.append("network_id = :network_id")
                params["network_id"] = network_id

            if tags_include:
                where.append("tags ?& :tags_include")
                params["tags_include"] = tags_include

            if tags_exclude:
                where.append("tags ?| :tags_exclude")
                params["tags_exclude"] = tags_exclude

            if name:
                where.append("name = :name")
                params["name"] = name

            if model:
                where.append("model = :model")
                params["model"] = model

            if product_types_include:
                model_prefixes = []

                if "appliance" in product_types_include:
                    model_prefixes.append("MX")

                if "switch" in product_types_include:
                    model_prefixes.append("MS")

                if "wireless" in product_types_include:
                    model_prefixes.append("MR")

                if model_prefixes:
                    model_clauses = []

                    for i, prefix in enumerate(model_prefixes):
                        param_name = f"model_prefix_{i}"
                        model_clauses.append(f"model ILIKE :{param_name}")
                        params[param_name] = f"{prefix}%"

                    where.append("(" + " OR ".join(model_clauses) + ")")

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
    def sync(cls, org_id):
        results = cls.get(source="meraki", org_id = org_id)
        if not results:
            return "Failed to retrieve data from Meraki"

        for row in results:
            row.upsert()

        return f"Synced {len(results)} items from Meraki"
