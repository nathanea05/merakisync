from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from meraki_sync.config import get_config  # your config loader
from meraki_sync.db.models import Base
import meraki_sync.db.tables  # ensure tables are imported so metadata is populated


# Alembic Config object (reads values we set below)
config = context.config

# Logging (optional, but standard)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata Alembic uses for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    return get_config().db.get_dsn()


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
