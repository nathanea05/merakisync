"""Add provider column to meraki.uplink.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "uplink",
        sa.Column("provider", sa.String(), nullable=True),
        schema="meraki",
    )


def downgrade() -> None:
    op.drop_column("uplink", "provider", schema="meraki")
