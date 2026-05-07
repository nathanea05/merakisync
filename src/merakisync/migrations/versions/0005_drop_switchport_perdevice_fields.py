"""Drop switchport columns only available from the per-device endpoint.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-07

The Switchport sync uses GET /organizations/{org}/switch/ports/bySwitch,
which does not return isolationEnabled, portScheduleId, udld,
accessPolicyNumber, macAllowList, stormControlEnabled, adaptivePolicyGroupId,
peerSgtCapable, flexibleStackingEnabled, or daiTrusted.  Retaining those
columns causes every port to appear "changed" on every sync (legacy DB values
vs NULL from the org-level endpoint).  Dropping them makes the schema match
the actual sync source.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    "isolation_enabled",
    "port_schedule_id",
    "udld",
    "access_policy_number",
    "mac_allow_list",
    "storm_control_enabled",
    "adaptive_policy_group_id",
    "peer_sgt_capable",
    "flexible_stacking_enabled",
    "dai_trusted",
]


def upgrade() -> None:
    for col in _COLUMNS:
        op.drop_column("switchport", col, schema="meraki")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("switchport", sa.Column("isolation_enabled", sa.Boolean(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("port_schedule_id", sa.String(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("udld", sa.String(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("access_policy_number", sa.Integer(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("mac_allow_list", sa.Text(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("storm_control_enabled", sa.Boolean(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("adaptive_policy_group_id", sa.String(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("peer_sgt_capable", sa.Boolean(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("flexible_stacking_enabled", sa.Boolean(), nullable=True), schema="meraki")
    op.add_column("switchport", sa.Column("dai_trusted", sa.Boolean(), nullable=True), schema="meraki")
