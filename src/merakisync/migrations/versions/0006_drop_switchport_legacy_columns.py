"""Drop legacy switchport columns not present in the merakisync schema.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-07

The production switchport table was created by a pre-Alembic legacy system
that tracked additional per-device endpoint fields as separate columns.
These columns were never added to the merakisync Alembic schema (migrations
0001–0005) and are not part of the Switchport model.  Their presence causes
_data_equal to fail on every row (key-set mismatch), marking every port as
changed on every sync.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    "stp_port_fast_trunk",
    "link_negotiation_capabilities",
    "schedule",
    "mac_whitelist_limit",
    "adaptive_policy_group",
    "profile",
    "module",
    "mirror",
    "dot3az",
    "high_speed",
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.drop_column("switchport", col, schema="meraki")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("switchport", sa.Column("stp_port_fast_trunk", sa.Boolean(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("link_negotiation_capabilities", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("schedule", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("mac_whitelist_limit", sa.Integer(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("adaptive_policy_group", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("profile", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("module", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("mirror", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("dot3az", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("high_speed", sa.Text(), nullable=True), schema="meraki")
