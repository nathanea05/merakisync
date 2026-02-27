from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_head() -> None:
    root = Path(__file__).resolve().parents[3]  # .../src/meraki_sync/db/migrate.py -> project root
    ini_path = root / "alembic.ini"

    cfg = Config(str(ini_path))
    command.upgrade(cfg, "head")
