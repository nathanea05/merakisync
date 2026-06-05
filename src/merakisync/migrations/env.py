from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object — gives access to values in alembic.ini
config = context.config

# Wire up Python logging from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the DSN from merakisync's own config so we never have to store it
# in alembic.ini or pass it on the command line.
def _get_dsn() -> str:
    from merakisync.config import get_config
    from merakisync.exceptions import MissingConfigError
    conf = get_config()
    if conf.db is None:
        raise MissingConfigError(
            "Database is not configured. Run `merakisync init --database`."
        )
    return conf.db.get_dsn()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without connecting)."""
    url = _get_dsn()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="meraki",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect and execute)."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_dsn()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            version_table_schema="meraki",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
