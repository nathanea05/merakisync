from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from meraki_sync.config import get_config  # whatever your loader is called


def get_engine(dsn: str | None = None) -> Engine:
    if dsn is None:
        dsn = get_config().db.get_dsn()  # or config.get_dsn()
    return create_engine(dsn, pool_pre_ping=True)
