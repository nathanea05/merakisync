"""Add meraki.device_lldp_cdp table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-26

Stores per-port CDP and LLDP neighbor data from
GET /devices/{serial}/lldp_cdp.

SCD2 versioning: one active row per (serial, local_port) (active_to IS NULL).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE meraki.device_lldp_cdp (
            serial                    VARCHAR                  NOT NULL,
            local_port                VARCHAR                  NOT NULL,
            cdp_device_id             VARCHAR,
            cdp_port_id               VARCHAR,
            cdp_address               VARCHAR,
            cdp_management_address    VARCHAR,
            cdp_version               INTEGER,
            cdp_vlan_id               VARCHAR,
            cdp_platform              VARCHAR,
            cdp_native_vlan           VARCHAR,
            cdp_capabilities          VARCHAR,
            cdp_vtp_management_domain VARCHAR,
            cdp_system_name           VARCHAR,
            lldp_chassis_id           VARCHAR,
            lldp_port_id              VARCHAR,
            lldp_management_address   VARCHAR,
            lldp_management_vlan      VARCHAR,
            lldp_port_description     VARCHAR,
            lldp_system_name          VARCHAR,
            lldp_system_description   TEXT,
            lldp_port_vlan            VARCHAR,
            lldp_capabilities         VARCHAR,
            active_from               TIMESTAMP WITH TIME ZONE,
            active_to                 TIMESTAMP WITH TIME ZONE,
            last_seen                 TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute(
        "CREATE INDEX ix_device_lldp_cdp_pk_active "
        "ON meraki.device_lldp_cdp (serial, local_port, active_to)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meraki.device_lldp_cdp")
