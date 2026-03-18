# Library Imports
from dataclasses import dataclass
from typing import Optional

# Local Imports
from meraki_sync.meraki.models.base import MerakiObj
from meraki_sync import get_dashboard
from meraki_sync.db.engine import get_engine


@dataclass
class Device(MerakiObj):
    __table__ = "device"
    __pk__ = ("serial",)

    # Natural key
    serial: str

    # Meraki fields
    network_id: Optional[str] = None
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None
    notes: Optional[str] = None

    tags: Optional[list[str]] = None

    model: Optional[str] = None
    mac: Optional[str] = None
    lan_ip: Optional[str] = None
    firmware: Optional[str] = None
    floor_plan_id: Optional[str] = None

    details: Optional[list[dict]] = None
    beacon_id_params: Optional[dict] = None

    status: Optional[str] = None

    # Your pattern (minimal required set)
    __required_fields__ = {"serial"}


    @classmethod
    def get_all(cls, org_id: str, source: str = "database") -> list[cls]:
        """Retrieve all devices in an organization"""

        if source == "meraki":
            dashboard = get_dashboard()
            raw_devices = dashboard.organizations.getOrganizationDevices(org_id)
        
        elif source == "database":
            engine = get_engine()
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")

        device = cls.from_row({"test": "test"})
        return [device]

    @classmethod
    def get_one(cls, org_id: str, serial: str, source: str = "database") -> cls:
        return
