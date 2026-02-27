from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from psycopg_pool import ConnectionPool
from psycopg import connect, Connection
from psycopg.errors import OperationalError

from meraki_sync.config import get_config

class DatabaseConnectionError(RuntimeError):
    """Raised when the Database connection failes"""

@lru_cache(maxsize=8)
def get_pool(dsn: str | None = None) -> ConnectionPool:
    if dsn is None:
        dsn = get_config().db.get_dsn()

    return ConnectionPool(
        conninfo=dsn,
        min_size=1,
        max_size=10,
        timeout=10,
    )


@contextmanager
def get_conn(dsn: str | None = None) -> Iterator[Connection]:
    pool = get_pool(dsn)
    with pool.connection() as conn:
        yield conn


def close_pool() -> None:
    pool = get_pool()
    pool.close()
    get_pool.cache_clear()


def validate_connection(dsn: str | None = None) -> None:
    """
    Attempt to connect to Postgres and run a simple query.

    Raises DatabaseConnectionError if invalid.
    """
    if not dsn:
        dsn = get_config().db.get_dsn()
    try:
        with connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
    except OperationalError as e:
        raise DatabaseConnectionError(
                f"Database Connection failed"
                ) from e

