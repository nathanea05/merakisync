"""Add psk column to meraki.ssid.

Revision ID: 0008
Revises: 0008
Create Date: 2026-06-04

The psk field is returned by GET /networks/{networkId}/wireless/ssids for
SSIDs using authMode='psk'. Read-only API keys receive a masked value.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE meraki.ssid ADD COLUMN IF NOT EXISTS psk VARCHAR"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE meraki.ssid DROP COLUMN IF EXISTS psk"
    )
