"""Convert tags and product_types columns from TEXT to JSONB.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04

Enables JSONB containment operators (?& / ?|) for tag and product-type
filtering in Network.get() and Device.get() with source='database'.

Affected columns:
  meraki.network.tags              TEXT → JSONB
  meraki.network.product_types     TEXT → JSONB
  meraki.device.tags               TEXT → JSONB

All existing values are valid JSON arrays so the USING cast is safe.
PostgreSQL assignment casts (text → jsonb in INSERT/UPDATE) continue to
work, so no application-side changes are required for writes.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE meraki.network "
        "ALTER COLUMN tags TYPE JSONB USING tags::jsonb"
    )
    op.execute(
        "ALTER TABLE meraki.network "
        "ALTER COLUMN product_types TYPE JSONB USING product_types::jsonb"
    )
    op.execute(
        "ALTER TABLE meraki.device "
        "ALTER COLUMN tags TYPE JSONB USING tags::jsonb"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE meraki.network "
        "ALTER COLUMN tags TYPE TEXT USING tags::text"
    )
    op.execute(
        "ALTER TABLE meraki.network "
        "ALTER COLUMN product_types TYPE TEXT USING product_types::text"
    )
    op.execute(
        "ALTER TABLE meraki.device "
        "ALTER COLUMN tags TYPE TEXT USING tags::text"
    )
