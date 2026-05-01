from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from merakisync.exceptions import DatabaseConnectionError


@lru_cache(maxsize=8)
def get_engine(dsn: str | None = None) -> Engine:
    """Return a cached SQLAlchemy engine for *dsn*.

    On first call for a given DSN the engine is created and cached.
    Subsequent calls with the same DSN return the same engine instance,
    which means the connection pool is reused across the entire process.

    Args:
        dsn: PostgreSQL DSN string. If omitted, the DSN is read from the
             merakisync configuration file / env vars.
    """
    if dsn is None:
        # Import here to avoid a circular dependency at module load time.
        from merakisync.config import get_config
        dsn = get_config().db.get_dsn()

    return create_engine(
        dsn,
        pool_pre_ping=True,   # verify connections before handing them out
        pool_size=5,
        max_overflow=10,
    )


def _get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session(engine: Engine | None = None) -> Iterator[Session]:
    """Context manager that yields a SQLAlchemy Session and handles commit/rollback.

    Usage::

        with get_session() as session:
            session.execute(text("SELECT 1"))
    """
    if engine is None:
        engine = get_engine()
    factory = _get_session_factory(engine)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def validate_connection(dsn: str | None = None) -> None:
    """Attempt a lightweight query to confirm the database is reachable.

    Raises:
        DatabaseConnectionError: if the connection or query fails.
    """
    try:
        engine = get_engine(dsn)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError("Database connection failed.") from exc
