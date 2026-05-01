"""Initial schema — all merakisync tables.

Revision ID: 0001
Revises:
Create Date: 2026-04-30
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS meraki")

    # ------------------------------------------------------------------
    # organization
    # ------------------------------------------------------------------
    op.create_table(
        "organization",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("api", sa.Text(), nullable=True),          # JSON
        sa.Column("licensing", sa.Text(), nullable=True),    # JSON
        sa.Column("cloud", sa.Text(), nullable=True),        # JSON
        sa.Column("management", sa.Text(), nullable=True),   # JSON
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_organization_id_active",
        "organization",
        ["id", "active_to"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # network
    # ------------------------------------------------------------------
    op.create_table(
        "network",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("product_types", sa.Text(), nullable=True),   # JSON array
        sa.Column("time_zone", sa.String(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),            # JSON array
        sa.Column("enrollment_string", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_bound_to_config_template", sa.Boolean(), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_network_id_active",
        "network",
        ["id", "active_to"],
        schema="meraki",
    )
    op.create_index(
        "ix_network_org_id",
        "network",
        ["organization_id"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # device
    # ------------------------------------------------------------------
    op.create_table(
        "device",
        sa.Column("serial", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("network_id", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),            # JSON array
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("mac", sa.String(), nullable=True),
        sa.Column("lan_ip", sa.String(), nullable=True),
        sa.Column("firmware", sa.String(), nullable=True),
        sa.Column("floor_plan_id", sa.String(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),         # JSON array
        sa.Column("beacon_id_params", sa.Text(), nullable=True),# JSON
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_device_serial_active",
        "device",
        ["serial", "active_to"],
        schema="meraki",
    )
    op.create_index(
        "ix_device_network_id",
        "device",
        ["network_id"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # switchport
    # ------------------------------------------------------------------
    op.create_table(
        "switchport",
        sa.Column("serial", sa.String(), nullable=False),
        sa.Column("port_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),            # JSON array
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("poe_enabled", sa.Boolean(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("vlan", sa.Integer(), nullable=True),
        sa.Column("voice_vlan", sa.Integer(), nullable=True),
        sa.Column("allowed_vlans", sa.String(), nullable=True),
        sa.Column("isolation_enabled", sa.Boolean(), nullable=True),
        sa.Column("rstp_enabled", sa.Boolean(), nullable=True),
        sa.Column("stp_guard", sa.String(), nullable=True),
        sa.Column("link_negotiation", sa.String(), nullable=True),
        sa.Column("port_schedule_id", sa.String(), nullable=True),
        sa.Column("udld", sa.String(), nullable=True),
        sa.Column("access_policy_type", sa.String(), nullable=True),
        sa.Column("access_policy_number", sa.Integer(), nullable=True),
        sa.Column("mac_allow_list", sa.Text(), nullable=True),           # JSON array
        sa.Column("sticky_mac_allow_list", sa.Text(), nullable=True),    # JSON array
        sa.Column("sticky_mac_allow_list_limit", sa.Integer(), nullable=True),
        sa.Column("storm_control_enabled", sa.Boolean(), nullable=True),
        sa.Column("adaptive_policy_group_id", sa.String(), nullable=True),
        sa.Column("peer_sgt_capable", sa.Boolean(), nullable=True),
        sa.Column("flexible_stacking_enabled", sa.Boolean(), nullable=True),
        sa.Column("dai_trusted", sa.Boolean(), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_switchport_pk_active",
        "switchport",
        ["serial", "port_id", "active_to"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # uplink
    # ------------------------------------------------------------------
    op.create_table(
        "uplink",
        sa.Column("serial", sa.String(), nullable=False),
        sa.Column("interface", sa.String(), nullable=False),
        sa.Column("network_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("gateway", sa.String(), nullable=True),
        sa.Column("public_ip", sa.String(), nullable=True),
        sa.Column("primary_dns", sa.String(), nullable=True),
        sa.Column("secondary_dns", sa.String(), nullable=True),
        sa.Column("ip_assigned_by", sa.String(), nullable=True),
        sa.Column("signal_stat", sa.Text(), nullable=True),     # JSON
        sa.Column("connection_type", sa.String(), nullable=True),
        sa.Column("apn", sa.String(), nullable=True),
        sa.Column("dns1", sa.String(), nullable=True),
        sa.Column("dns2", sa.String(), nullable=True),
        sa.Column("signal_type", sa.String(), nullable=True),
        sa.Column("mtu", sa.Integer(), nullable=True),
        sa.Column("iccid", sa.String(), nullable=True),
        sa.Column("imsi", sa.String(), nullable=True),
        sa.Column("msisdn", sa.String(), nullable=True),
        sa.Column("mcc", sa.String(), nullable=True),
        sa.Column("mnc", sa.String(), nullable=True),
        sa.Column("roaming", sa.Text(), nullable=True),         # JSON
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_uplink_pk_active",
        "uplink",
        ["serial", "interface", "active_to"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # uplink_usage  (no SCD2 — simple UPSERT per month/year)
    # ------------------------------------------------------------------
    op.create_table(
        "uplink_usage",
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column("serial", sa.String(), nullable=False),
        sa.Column("interface", sa.String(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("sent", sa.BigInteger(), nullable=True),
        sa.Column("received", sa.BigInteger(), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint(
            "network_id", "serial", "interface", "month", "year",
            name="pk_uplink_usage",
        ),
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # dhcp_server_policy
    # ------------------------------------------------------------------
    op.create_table(
        "dhcp_server_policy",
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column("default_policy", sa.String(), nullable=True),
        sa.Column("blocked_servers", sa.Text(), nullable=True),        # JSON array
        sa.Column("allowed_servers", sa.Text(), nullable=True),        # JSON array
        sa.Column("always_allowed_servers", sa.Text(), nullable=True), # JSON array
        sa.Column("arp_inspection", sa.Text(), nullable=True),         # JSON
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_dhcp_policy_network_active",
        "dhcp_server_policy",
        ["network_id", "active_to"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # alert
    # ------------------------------------------------------------------
    op.create_table(
        "alert",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("category_type", sa.String(), nullable=True),
        sa.Column("network_id", sa.String(), nullable=True),
        sa.Column("network_name", sa.String(), nullable=True),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.String(), nullable=True),
        sa.Column("dismissed_at", sa.String(), nullable=True),
        sa.Column("device_type", sa.String(), nullable=True),
        sa.Column("alert_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),               # JSON
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_alert_id_active",
        "alert",
        ["id", "active_to"],
        schema="meraki",
    )
    op.create_index(
        "ix_alert_org_id",
        "alert",
        ["org_id"],
        schema="meraki",
    )

    # ------------------------------------------------------------------
    # l3_firewall_rule
    # ------------------------------------------------------------------
    op.create_table(
        "l3_firewall_rule",
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column("rule_order", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("policy", sa.String(), nullable=True),
        sa.Column("protocol", sa.String(), nullable=True),
        sa.Column("dest_port", sa.String(), nullable=True),
        sa.Column("dest_cidr", sa.String(), nullable=True),
        sa.Column("src_port", sa.String(), nullable=True),
        sa.Column("src_cidr", sa.String(), nullable=True),
        sa.Column("syslog_enabled", sa.Boolean(), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_l3_rule_pk_active",
        "l3_firewall_rule",
        ["network_id", "rule_order", "active_to"],
        schema="meraki",
    )


def downgrade() -> None:
    op.drop_table("l3_firewall_rule", schema="meraki")
    op.drop_table("alert", schema="meraki")
    op.drop_table("dhcp_server_policy", schema="meraki")
    op.drop_table("uplink_usage", schema="meraki")
    op.drop_table("uplink", schema="meraki")
    op.drop_table("switchport", schema="meraki")
    op.drop_table("device", schema="meraki")
    op.drop_table("network", schema="meraki")
    op.drop_table("organization", schema="meraki")
