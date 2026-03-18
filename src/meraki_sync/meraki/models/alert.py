from dataclasses import dataclass
from typing import ClassVar
from meraki_sync.meraki.models.base import MerakiObj


@dataclass(frozen=True, slots=True)
class Alert(MerakiObj):
    __schema__ = "service_now"
    __table_name__ = "meraki_alert"
    __pk__ = ("id",)

    __mapping_override__ = {
            "alert_type": "type"
            }

    id: str
    category_type: str
    network_id: str
    network_name: str
    started_at: str
    resolved_at: str
    dismissed_at: str
    device_type: str
    alert_type: str
    title: str
    description: str
    severity: str
    scope: dict

    org_id: str
    
