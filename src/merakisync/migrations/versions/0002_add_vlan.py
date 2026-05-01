"""Add meraki.vlan table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-01
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vlan",
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("appliance_ip", sa.String(), nullable=True),
        sa.Column("subnet", sa.String(), nullable=True),
        sa.Column("interface_id", sa.String(), nullable=True),
        sa.Column("group_policy_id", sa.String(), nullable=True),
        sa.Column("template_vlan_type", sa.String(), nullable=True),
        sa.Column("cidr", sa.String(), nullable=True),
        sa.Column("mask", sa.Integer(), nullable=True),
        sa.Column("dhcp_handling", sa.String(), nullable=True),
        sa.Column("dhcp_lease_time", sa.String(), nullable=True),
        sa.Column("dhcp_boot_options_enabled", sa.Boolean(), nullable=True),
        sa.Column("dhcp_boot_next_server", sa.String(), nullable=True),
        sa.Column("dhcp_boot_filename", sa.String(), nullable=True),
        sa.Column("dns_nameservers", sa.String(), nullable=True),
        sa.Column("vpn_nat_subnet", sa.String(), nullable=True),
        sa.Column("dhcp_relay_server_ips", sa.Text(), nullable=True),   # JSON array
        sa.Column("fixed_ip_assignments", sa.Text(), nullable=True),    # JSON object
        sa.Column("reserved_ip_ranges", sa.Text(), nullable=True),      # JSON array
        sa.Column("dhcp_options", sa.Text(), nullable=True),            # JSON array
        sa.Column("mandatory_dhcp", sa.Text(), nullable=True),          # JSON object
        sa.Column("ipv6", sa.Text(), nullable=True),                    # JSON object
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_vlan_pk_active",
        "vlan",
        ["network_id", "vlan_id", "active_to"],
        schema="meraki",
    )


def downgrade() -> None:
    op.drop_index("ix_vlan_pk_active", table_name="vlan", schema="meraki")
    op.drop_table("vlan", schema="meraki")
