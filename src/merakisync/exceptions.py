from __future__ import annotations


class MissingConfigError(Exception):
    """Config file not found or required keys are absent. Run `merakisync init`."""


class ConfigWriteError(RuntimeError):
    """Config file could not be written, usually a permissions or OS error."""


class MerakiConnectionError(RuntimeError):
    """Meraki Dashboard API connection failed, typically an invalid API key."""


class DatabaseConnectionError(RuntimeError):
    """PostgreSQL connection failed."""


class UpsertError(RuntimeError):
    """A database upsert could not be completed."""
