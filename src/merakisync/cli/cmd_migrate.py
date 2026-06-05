from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def _check_db_configured() -> None:
    from merakisync.config import get_config
    from merakisync.exceptions import MissingConfigError
    conf = get_config()
    if conf.db is None:
        raise MissingConfigError(
            "Database is not configured. Run `merakisync init --database`."
        )


def run(revision: str = "head") -> None:
    """Run Alembic migrations up to *revision* (default: head).

    Reads the DSN from the merakisync configuration so no separate
    database URL needs to be passed on the command line.

    Works in three environments:
        - Development (src layout): importlib.resources resolves to src/
        - Pip install: importlib.resources resolves to site-packages/
        - PyInstaller frozen binary: data files are extracted to sys._MEIPASS
    """
    try:
        from merakisync.exceptions import MissingConfigError
        _check_db_configured()
    except MissingConfigError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    try:
        import pathlib
        from alembic import command
        from alembic.config import Config as AlembicConfig

        if getattr(sys, "frozen", False):
            # PyInstaller one-file binary: migrations/ is extracted alongside
            # the merakisync package under sys._MEIPASS at startup.
            migrations_dir = str(pathlib.Path(sys._MEIPASS) / "merakisync" / "migrations")
        else:
            import importlib.resources as pkg_resources
            import merakisync
            migrations_dir = str(pkg_resources.files(merakisync) / "migrations")

        # Use a bare AlembicConfig (no ini file) and set every required option
        # programmatically.  This avoids any need to locate or bundle alembic.ini.
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", migrations_dir)
        command.upgrade(alembic_cfg, revision)
        logger.info("Migrations applied to revision: %s", revision)
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        sys.exit(1)
