from __future__ import annotations

import re

_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(name: str) -> str:
    """Convert a camelCase or PascalCase string to snake_case.

    Examples:
        organizationId  -> organization_id
        isBoundToConfigTemplate -> is_bound_to_config_template
        publicIP -> public_i_p  (preserve existing behaviour for edge cases)
    """
    return _CAMEL_RE.sub("_", name).lower()


def snake_to_camel(name: str) -> str:
    """Convert a snake_case string to camelCase.

    Examples:
        organization_id -> organizationId
        is_bound_to_config_template -> isBoundToConfigTemplate
        name -> name
    """
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
