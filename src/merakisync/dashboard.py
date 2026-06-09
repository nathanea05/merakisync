from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import meraki
from meraki.exceptions import APIError

from merakisync.config import get_config
from merakisync.exceptions import MerakiConnectionError


# ---------------------------------------------------------------------------
# API call counter
# ---------------------------------------------------------------------------
# The Meraki SDK emits one INFO record per HTTP request in the form
# "{METHOD} {url}" (e.g. "GET https://api.meraki.com/...").  We attach a
# lightweight handler to the SDK's logger to count those records.  This
# captures every real HTTP request including pagination pages and retries.

_HTTP_METHODS = ("GET ", "POST ", "PUT ", "DELETE ", "PATCH ")


class _ApiCallCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.count: int = 0

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage().startswith(_HTTP_METHODS):
            self.count += 1


_counter = _ApiCallCounter()

# Attach once at module load.  propagate=False keeps SDK log lines out of the
# application's log output (same effect as the previous suppress_logging=True).
_meraki_logger = logging.getLogger("meraki")
_meraki_logger.setLevel(logging.INFO)
_meraki_logger.propagate = False
_meraki_logger.addHandler(_counter)


def get_api_call_count() -> int:
    """Return the total number of Meraki HTTP requests made this process."""
    return _counter.count


def reset_api_call_count() -> None:
    """Reset the API call counter to zero."""
    _counter.count = 0


@dataclass(frozen=True)
class DashboardDefaults:
    """Reasonable defaults for the Meraki SDK"""
    suppress_logging: bool = False
    inherit_logging_config: bool = True
    print_console: bool = False
    output_log: bool = False
    wait_on_rate_limit: bool = True
    maximum_retries: int = 20


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
            inherit_logging_config=defaults.inherit_logging_config,
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

def get_dashboard(api_key: str | None = None) -> meraki.DashboardAPI:
    if api_key is None:
        from merakisync.exceptions import MissingConfigError
        conf = get_config()
        if conf.meraki_api_key is None:
            raise MissingConfigError(
                "Meraki API key is not configured. Run `merakisync init --meraki`."
            )
        api_key = conf.meraki_api_key
    return _get_cached_dashboard(api_key)


def reset_dashboard_cache() -> None:
    """Clears all cached dahboard (helpful if changing API key during runtime)"""
    _get_cached_dashboard.cache_clear()
