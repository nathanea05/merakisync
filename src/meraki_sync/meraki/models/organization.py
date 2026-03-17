from dataclasses import dataclass
from typing import ClassVar
from meraki_sync.meraki.models.base import MerakiObj

@dataclass(frozen=True, slots=True)
class Organization(MerakiObj):
    __table_name__: ClassVar[str] = "organization"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    id: str
    name: str
    url: str
    api: dict
    licensing: dict
    cloud: dict
    management: dict

