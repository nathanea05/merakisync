from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def run(revision: str = "head") -> None:
    """Run Alembic migrations up to *revision* (default: head).

    Reads the DSN from the merakisync configuration so no separate
    database URL needs to be passed on the command line.
    """
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        import importlib.resources as pkg_resources
        import merakisync

        alembic_ini = str(
            pkg_resources.files(merakisync).parent.parent / "alembic.ini"
        )
        alembic_cfg = AlembicConfig(alembic_ini)
        # Override script_location with an absolute path so migrations work
        # regardless of the current working directory.
        migrations_dir = str(pkg_resources.files(merakisync) / "migrations")
        alembic_cfg.set_main_option("script_location", migrations_dir)
        command.upgrade(alembic_cfg, revision)
        logger.info("Migrations applied to revision: %s", revision)
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        sys.exit(1)
