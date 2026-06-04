"""Reconcile legacy production schema to merakisync 0002 state.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-04

This migration brings a pre-Alembic production database into alignment with
the schema defined by migrations 0001 and 0002.  It is safe to run against
the live production database provided the pre-run checklist is satisfied:

Pre-run checklist
-----------------
1. Run ``merakisync migrate stamp 0002`` against the target database.
   (or insert directly: INSERT INTO meraki.alembic_version VALUES ('0002'))
   This tells Alembic that 0001 and 0002 have already been applied so that
   only this migration runs.
2. Confirm all vlan.id values are numeric (no non-integer strings).
3. Take a database backup before running.

Changes made
------------
- Creates meraki.alert table (was absent from the legacy schema).
- Creates meraki.l3_firewall_rule table (was absent from the legacy schema).
- Adds 7 query indexes that migration 0001 would have created.
- switchport: renames device_serial -> serial; drops legacy PK and unique
  index; creates ix_switchport_pk_active.
- uplink_usage: renames device_serial -> serial and updated_at -> last_seen;
  drops last_day column; replaces PK with pk_uplink_usage.
- vlan: renames id -> vlan_id and casts text -> integer; adds network_id
  (nullable — existing rows have no network_id and will be superseded by
  fresh SCD2 rows on the next sync); drops legacy PK and unique index;
  creates ix_vlan_pk_active.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names(schema="meraki"))

    def col_names(table: str) -> set[str]:
        return {c["name"] for c in inspector.get_columns(table, schema="meraki")}

    def idx_names(table: str) -> set[str]:
        return {i["name"] for i in inspector.get_indexes(table, schema="meraki")}

    # ------------------------------------------------------------------
    # Create tables absent from the legacy production schema
    # ------------------------------------------------------------------
    if "alert" not in existing_tables:
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
            sa.Column("scope", sa.Text(), nullable=True),
            sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
            schema="meraki",
        )
    if "ix_alert_id_active" not in idx_names("alert"):
        op.create_index("ix_alert_id_active", "alert", ["id", "active_to"], schema="meraki")
    if "ix_alert_org_id" not in idx_names("alert"):
        op.create_index("ix_alert_org_id", "alert", ["org_id"], schema="meraki")

    if "l3_firewall_rule" not in existing_tables:
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
    if "ix_l3_rule_pk_active" not in idx_names("l3_firewall_rule"):
        op.create_index(
            "ix_l3_rule_pk_active",
            "l3_firewall_rule",
            ["network_id", "rule_order", "active_to"],
            schema="meraki",
        )

    # ------------------------------------------------------------------
    # Add query indexes that migration 0001 defines but production lacked
    # ------------------------------------------------------------------
    for _table, _idx, _cols in [
        ("organization", "ix_organization_id_active", ["id", "active_to"]),
        ("network",       "ix_network_id_active",     ["id", "active_to"]),
        ("network",       "ix_network_org_id",        ["organization_id"]),
        ("device",        "ix_device_serial_active",  ["serial", "active_to"]),
        ("device",        "ix_device_network_id",     ["network_id"]),
        ("uplink",        "ix_uplink_pk_active",      ["serial", "interface", "active_to"]),
        ("dhcp_server_policy", "ix_dhcp_policy_network_active", ["network_id", "active_to"]),
    ]:
        if _idx not in idx_names(_table):
            op.create_index(_idx, _table, _cols, schema="meraki")

    # ------------------------------------------------------------------
    # switchport: device_serial -> serial
    #
    # Production had a PK on (device_serial, port_id, active_from) and a
    # unique partial index on (device_serial, port_id) WHERE active_to IS NULL.
    # Migration 0001 expects column serial with a plain btree index on
    # (serial, port_id, active_to).  No DB-level PK is added back — the
    # SCD2 upsert logic enforces uniqueness in Python.
    # ------------------------------------------------------------------
    if "device_serial" in col_names("switchport"):
        op.drop_constraint("switchport_pkey", "switchport", schema="meraki", type_="primary")
        op.drop_index("switchport_one_active_per_device_port", table_name="switchport", schema="meraki")
        op.alter_column("switchport", "device_serial", new_column_name="serial", schema="meraki")
    if "ix_switchport_pk_active" not in idx_names("switchport"):
        op.create_index(
            "ix_switchport_pk_active",
            "switchport",
            ["serial", "port_id", "active_to"],
            schema="meraki",
        )

    # ------------------------------------------------------------------
    # uplink_usage: fix column names and PK
    #
    # Legacy: (device_serial, updated_at, last_day)
    #   PK: (network_id, device_serial, interface, month, year)
    # Target: (serial, last_seen)
    #   PK: (network_id, serial, interface, month, year)
    # last_day had no equivalent in merakisync and is dropped.
    # ------------------------------------------------------------------
    uu_cols = col_names("uplink_usage")
    if "device_serial" in uu_cols:
        op.drop_constraint("uplink_usage_pk", "uplink_usage", schema="meraki", type_="primary")
        op.alter_column("uplink_usage", "device_serial", new_column_name="serial", schema="meraki")
    if "updated_at" in uu_cols:
        op.alter_column("uplink_usage", "updated_at", new_column_name="last_seen", schema="meraki")
    if "last_day" in uu_cols:
        op.drop_column("uplink_usage", "last_day", schema="meraki")
    uu_pk = inspector.get_pk_constraint("uplink_usage", schema="meraki")
    if uu_pk.get("name") != "pk_uplink_usage":
        op.create_primary_key(
            "pk_uplink_usage",
            "uplink_usage",
            ["network_id", "serial", "interface", "month", "year"],
            schema="meraki",
        )

    # ------------------------------------------------------------------
    # vlan: id (text) -> vlan_id (integer); add network_id
    #
    # Legacy: PK on (id, active_from); unique partial index on (id).
    # Target: no DB PK; index ix_vlan_pk_active on (network_id, vlan_id, active_to).
    #
    # network_id is added as nullable.  Existing rows have no network_id
    # and will remain with network_id = NULL.  On the next sync, fresh rows
    # with correct (network_id, vlan_id) pairs are inserted via SCD2; the
    # old NULL-network_id rows are not touched and eventually become stale
    # history.  The index on (network_id, vlan_id, active_to) enables the
    # SCD2 lookup to find current rows efficiently.
    # ------------------------------------------------------------------
    vlan_cols = col_names("vlan")
    if "id" in vlan_cols:
        op.drop_constraint("vlan_pkey", "vlan", schema="meraki", type_="primary")
        op.drop_index("vlan_one_active_per_id", table_name="vlan", schema="meraki")
        op.alter_column("vlan", "id", new_column_name="vlan_id", schema="meraki")
        op.execute(
            "ALTER TABLE meraki.vlan ALTER COLUMN vlan_id TYPE integer USING vlan_id::integer"
        )
    if "network_id" not in vlan_cols:
        op.add_column("vlan", sa.Column("network_id", sa.String(), nullable=True), schema="meraki")
    if "ix_vlan_pk_active" not in idx_names("vlan"):
        op.create_index(
            "ix_vlan_pk_active",
            "vlan",
            ["network_id", "vlan_id", "active_to"],
            schema="meraki",
        )


def downgrade() -> None:
    # Reverses all changes.  Note: vlan rows written with a non-null network_id
    # after the upgrade will have network_id dropped — data loss is expected on
    # downgrade of the vlan table.
    op.drop_index("ix_vlan_pk_active", table_name="vlan", schema="meraki")
    op.drop_column("vlan", "network_id", schema="meraki")
    op.execute(
        "ALTER TABLE meraki.vlan ALTER COLUMN vlan_id TYPE text USING vlan_id::text"
    )
    op.alter_column("vlan", "vlan_id", new_column_name="id", schema="meraki")
    op.create_primary_key("vlan_pkey", "vlan", ["id", "active_from"], schema="meraki")

    op.drop_constraint("pk_uplink_usage", "uplink_usage", schema="meraki", type_="primary")
    op.add_column(
        "uplink_usage",
        sa.Column("last_day", sa.BigInteger(), nullable=True),
        schema="meraki",
    )
    op.alter_column("uplink_usage", "last_seen", new_column_name="updated_at", schema="meraki")
    op.alter_column("uplink_usage", "serial", new_column_name="device_serial", schema="meraki")
    op.create_primary_key(
        "uplink_usage_pk",
        "uplink_usage",
        ["network_id", "device_serial", "interface", "month", "year"],
        schema="meraki",
    )

    op.drop_index("ix_switchport_pk_active", table_name="switchport", schema="meraki")
    op.alter_column("switchport", "serial", new_column_name="device_serial", schema="meraki")
    op.create_primary_key(
        "switchport_pkey",
        "switchport",
        ["device_serial", "port_id", "active_from"],
        schema="meraki",
    )

    op.drop_index("ix_dhcp_policy_network_active", table_name="dhcp_server_policy", schema="meraki")
    op.drop_index("ix_uplink_pk_active", table_name="uplink", schema="meraki")
    op.drop_index("ix_device_network_id", table_name="device", schema="meraki")
    op.drop_index("ix_device_serial_active", table_name="device", schema="meraki")
    op.drop_index("ix_network_org_id", table_name="network", schema="meraki")
    op.drop_index("ix_network_id_active", table_name="network", schema="meraki")
    op.drop_index("ix_organization_id_active", table_name="organization", schema="meraki")

    op.drop_index("ix_l3_rule_pk_active", table_name="l3_firewall_rule", schema="meraki")
    op.drop_table("l3_firewall_rule", schema="meraki")
    op.drop_index("ix_alert_org_id", table_name="alert", schema="meraki")
    op.drop_index("ix_alert_id_active", table_name="alert", schema="meraki")
    op.drop_table("alert", schema="meraki")
