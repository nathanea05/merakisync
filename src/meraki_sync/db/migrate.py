from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_head() -> None:
    root = Path(__file__).resolve().parents[3]  # .../src/meraki_sync/db/migrate.py -> project root
    migrations_dir = Path(__file__).resolve().parent / "migrations"

    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    command.upgrade(cfg, "head")
