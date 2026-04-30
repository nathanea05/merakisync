from dataclasses import dataclass
from typing import ClassVar, Literal, TypeVar, Type
from merakisync.models.base import MerakiObj
from merakisync import get_dashboard, get_engine
from datetime import datetime
from sqlalchemy import text

I = TypeVar("I", bound="Uplink")

@dataclass(frozen=True, slots=True)
class Uplink(MerakiObj):
    __table_name__ = "uplink"
    __pk__ = ("serial", "interface")
    __mapping_override__ = {}

    network_id: str
    serial: str
    interface: str

    status: str | None = None
    ip: str | None = None
    gateway: str | None = None
    public_ip: str | None = None
    primary_dns: str | None = None
    secondary_dns: str | None = None
    ip_asigned_by: str | None = None
    registrant: str | None = None
    signal_stat: dict | None = None
    mcc: str | None = None
    mnc: str | None = None
    roaming: dict | None = None
    connection_type: str | None = None
    apn: str | None = None
    dns1: str | None = None
    dns2: str | None = None
    signal_type: str | None = None
    mtu: int | None = None
    iccid: str | None = None
    imsi: str | None = None
    msisdn: str | None = None


    @classmethod
    def get(cls: Type[I],
            org_id: str,
            source: Literal["database", "meraki"] = "database",
            ts: datetime | Literal["all"] | None = None,

            network_id: str | None = None,
            serial: str | None = None,
            interface: str | None = None,
            status: str | None = None,
            ip_assigned_by: str | None = None,
            ) -> list[I] | None:

        if ts and source == "meraki":
            raise ValueError("Cannot perform timestamped lookups when source is Meraki. Use source database instead.")

        if source == "meraki":
            dashboard_params: dict = {
                    "total_pages": "all",
                    }
            if network_id:
                dashboard_params["networkIds"] = [network_id,]
            if serial:
                dashboard_params["serials"] = [serial,]

            filtered_uplinks = []
            dashboard = get_dashboard()
            response = dashboard.organizations.getOrganizationUplinksStatuses(org_id, **dashboard_params)
            
            uplinks = []

            # Flatten Data
            for network_data in response:
                net_id = network_data.get("networkId")
                device_serial = network_data.get("serial")
                raw_uplinks = network_data.get("uplinks")

                for raw_uplink in raw_uplinks:
                    raw_uplink["networkId"] = net_id
                    raw_uplink["serial"] = device_serial
                    uplink = cls.from_dashboard(raw_uplink)
                    uplinks.append(uplink)


            # Filter uplinks
            for uplink in uplinks:
                if network_id and uplink.network_id != network_id:
                    continue
                if serial and uplink.serial != serial:
                    continue
                if interface and uplink.interface != interface:
                    continue
                if status and uplink.status != status:
                    continue
                if ip_assigned_by and uplink.ip_asigned_by != ip_assigned_by:
                    continue
                filtered_uplinks.append(uplink)
            return filtered_uplinks

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
