from __future__ import annotations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import sqlalchemy
from sqlalchemy.engine import Engine
from merakisync.config import get_config


class DatabaseConnectionError(RuntimeError):
    """Raised when the database connection fails"""


def get_engine(dsn: str | None = None) -> Engine:
    if dsn is None:
        dsn = get_config().db.get_dsn()
    return create_engine(dsn, pool_pre_ping=True)

def validate_connection(dsn: str | None = None) -> None:
    """
    Attempt to connect to Postgres and run a simple query.

    Raises DatabaseConnectionError if invalid.
    """
    if not dsn:
        dsn = get_config().db.get_dsn()
    engine = get_engine(dsn)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1;"))
    except SQLAlchemyError as e:
        raise DatabaseConnectionError(
                f"Database Connection Failed"
                ) from e

