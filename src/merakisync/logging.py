from __future__ import annotations

import logging
import os
import sys


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure root logger for merakisync.

    Output is written to stdout so it integrates cleanly with systemd
    (journald captures stdout) and cron (cron captures stdout/stderr).
    No ANSI colour codes are emitted so log lines are machine-readable.

    Precedence (highest to lowest):
        1. --quiet flag  → WARNING
        2. --verbose flag → DEBUG
        3. MERAKISYNC_LOG_LEVEL env var
        4. Default → INFO
    """
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        env_level = os.getenv("MERAKISYNC_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any handlers added before we configure (e.g. basicConfig from imports)
    root.handlers.clear()
    root.addHandler(handler)

    # Keep third-party loggers quiet unless we're in debug mode.
    # The meraki logger is intentionally omitted here — dashboard.py sets
    # propagate=False on it so SDK output never reaches application handlers,
    # but we need the logger level at INFO so the API call counter can receive
    # HTTP request records.
    if level > logging.DEBUG:
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
