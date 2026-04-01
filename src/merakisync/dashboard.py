from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import meraki
from meraki.exceptions import APIError

from merakisync.config import get_config


class MerakiConnectionError(RuntimeError):
    """Raised when the Meraki Dashboard Connection fails, typically due to an invalid API key"""


@dataclass(frozen=True)
class DashboardDefaults:
    """Reasonable defaults for the Meraki SDK"""
    suppress_logging: bool = True
    print_console: bool = False
    output_log: bool = False
    wait_on_rate_limit: bool = True
    maximum_retries: int = 10


DEFAULTS = DashboardDefaults()


def create_dashboard(
        api_key: str,
        *,
        defaults: DashboardDefaults = DEFAULTS,
        ) -> meraki.DashboardAPI:
    """Create a new Meraki Dashboard instance"""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("Meraki API Key cannot be empty")
    
    return meraki.DashboardAPI(
            api_key=api_key,
            suppress_logging=defaults.suppress_logging,
            print_console=defaults.print_console,
            output_log=defaults.output_log,
            wait_on_rate_limit=defaults.wait_on_rate_limit,
            maximum_retries=defaults.maximum_retries,
            )

def validate_api_key(api_key: str) -> None:
    """Validates a meraki api key by performing a cheap API call.
    Raises MerakiConnectionError if invalid."""
    dashboard = create_dashboard(api_key)

    try:
        dashboard.organizations.getOrganizations()
    except APIError as e:
        raise MerakiConnectionError(f"Meraki API Key Validation failed: {e}") from e

@lru_cache(maxsize=8)
def _get_cached_dashboard(api_key: str) -> meraki.DashboardAPI:
    return create_dashboard(api_key)

def get_dashboard(api_key: Optional[str|None] = None) -> meraki.DashboardAPI:
    if api_key is None:
        conf = get_config()
        api_key = conf.meraki_api_key
    return _get_cached_dashboard(api_key)


def reset_dashboard_cache() -> None:
    """Clears all cached dahboard (helpful if changing API key during runtime)"""
    _get_cached_dashboard.cache_clear()
