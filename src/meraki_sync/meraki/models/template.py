from dataclasses import dataclass
from typing import ClassVar
from meraki_sync.meraki.models.base import MerakiObj


@dataclass(frozen=True, slots=True)
class xyz(MerakiObj):
    __table_name__: ClassVar[str] = ""
    __pk__: ClassVar[tuple[str, ...]] = ("",)

    id: str
