"""Add meraki.ssid table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-04

Uses CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS so that this
migration is safe to run against databases that already have the ssid table
(e.g. production instances that pre-date Alembic management).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS meraki.ssid (
            network_id          VARCHAR                  NOT NULL,
            number              INTEGER                  NOT NULL,
            name                VARCHAR,
            enabled             BOOLEAN,
            splash_page         VARCHAR,
            ssid_admin_accessible BOOLEAN,
            local_auth          BOOLEAN,
            auth_mode           VARCHAR,
            encryption_mode     VARCHAR,
            wpa_encryption_mode VARCHAR,
            radius_servers      TEXT,
            radius_accounting_servers TEXT,
            radius_accounting_enabled BOOLEAN,
            radius_enabled      BOOLEAN,
            radius_attribute_for_group_policies VARCHAR,
            radius_failover_policy VARCHAR,
            radius_load_balancing_policy VARCHAR,
            ip_assignment_mode  VARCHAR,
            admin_splash_url    VARCHAR,
            splash_timeout      VARCHAR,
            walled_garden_enabled BOOLEAN,
            walled_garden_ranges TEXT,
            min_bitrate         INTEGER,
            band_selection      VARCHAR,
            per_client_bandwidth_limit_up   INTEGER,
            per_client_bandwidth_limit_down INTEGER,
            visible             BOOLEAN,
            available_on_all_aps BOOLEAN,
            availability_tags   TEXT,
            per_ssid_bandwidth_limit_up     INTEGER,
            per_ssid_bandwidth_limit_down   INTEGER,
            mandatory_dhcp_enabled BOOLEAN,
            active_from         TIMESTAMP WITH TIME ZONE,
            active_to           TIMESTAMP WITH TIME ZONE,
            last_seen           TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ssid_pk_active"
        " ON meraki.ssid (network_id, number, active_to)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meraki.ix_ssid_pk_active")
    op.execute("DROP TABLE IF EXISTS meraki.ssid")
