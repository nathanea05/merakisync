from dataclasses import dataclass
from typing import ClassVar
from meraki_sync.meraki.models.base import MerakiObj


@dataclass(frozen=True, slots=True)
class Network(MerakiObj):
    __table_name__: ClassVar[str] = "network"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)

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
