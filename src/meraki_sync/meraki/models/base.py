from __future__ import annotations

from typing import ClassVar, TypeVar, Any, Type
from dataclasses import fields, is_dataclass
import re

_CAMEL_RE = re.compile(r'(?<!^)(?=[A-Z])')

def camel_to_snake(name: str) -> str:
    return _CAMEL_RE.sub("_", name).lower()

class MerakiObj:
    __schema__: ClassVar[str] = "meraki"
    __mapping_override__: ClassVar[dict[str, str]] = {}

    @classmethod
    def from_dashboard(cls: Type[T], data: dict[str, Any]) -> T:
        """
        Convert a Meraki dashboard API response dict (camelCase)
        into a MerakiObj dataclass instance (snake_case)
        """

        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a dataclass")

        field_names = {f.name for f in fields(cls)}

        override = {
                dashboard_key: model_field
                for model_field, dashboard_key in cls.__mapping_override__.items()
                }

        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key in override:
                attr = override[key]
            else:
                attr = camel_to_snake(key)

            if attr in field_names:
                kwargs[attr] = value

        return cls(**kwargs)
