-- Migration 0003: Reconcile legacy production schema to merakisync 0002 state.
--
-- Run this script as the owner of the meraki schema tables (the 'meraki' role)
-- or as a PostgreSQL superuser (e.g. psql -U postgres -d pacs_engineering).
--
-- Pre-requisite: the alembic_version table must already exist and contain '0002'.
-- If you followed the merakisync migration guide, this was done before running
-- this script.

BEGIN;

-- ------------------------------------------------------------------
-- Create tables absent from the legacy production schema
-- ------------------------------------------------------------------

CREATE TABLE meraki.alert (
    id VARCHAR NOT NULL,
    org_id VARCHAR NOT NULL,
    category_type VARCHAR,
    network_id VARCHAR,
    network_name VARCHAR,
    started_at VARCHAR,
    resolved_at VARCHAR,
    dismissed_at VARCHAR,
    device_type VARCHAR,
    alert_type VARCHAR,
    title VARCHAR,
    description TEXT,
    severity VARCHAR,
    scope TEXT,
    active_from TIMESTAMP WITH TIME ZONE,
    active_to TIMESTAMP WITH TIME ZONE,
    last_seen TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_alert_id_active ON meraki.alert (id, active_to);
CREATE INDEX ix_alert_org_id ON meraki.alert (org_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON meraki.alert TO merakisync;

CREATE TABLE meraki.l3_firewall_rule (
    network_id VARCHAR NOT NULL,
    rule_order INTEGER NOT NULL,
    comment TEXT,
    policy VARCHAR,
    protocol VARCHAR,
    dest_port VARCHAR,
    dest_cidr VARCHAR,
    src_port VARCHAR,
    src_cidr VARCHAR,
    syslog_enabled BOOLEAN,
    active_from TIMESTAMP WITH TIME ZONE,
    active_to TIMESTAMP WITH TIME ZONE,
    last_seen TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_l3_rule_pk_active ON meraki.l3_firewall_rule (network_id, rule_order, active_to);

GRANT SELECT, INSERT, UPDATE, DELETE ON meraki.l3_firewall_rule TO merakisync;

-- ------------------------------------------------------------------
-- Add query indexes missing from the legacy schema
-- ------------------------------------------------------------------

CREATE INDEX ix_organization_id_active ON meraki.organization (id, active_to);
CREATE INDEX ix_network_id_active ON meraki.network (id, active_to);
CREATE INDEX ix_network_org_id ON meraki.network (organization_id);
CREATE INDEX ix_device_serial_active ON meraki.device (serial, active_to);
CREATE INDEX ix_device_network_id ON meraki.device (network_id);
CREATE INDEX ix_uplink_pk_active ON meraki.uplink (serial, interface, active_to);
CREATE INDEX ix_dhcp_policy_network_active ON meraki.dhcp_server_policy (network_id, active_to);

-- ------------------------------------------------------------------
-- switchport: rename device_serial -> serial
-- ------------------------------------------------------------------

ALTER TABLE meraki.switchport DROP CONSTRAINT switchport_pkey;
DROP INDEX meraki.switchport_one_active_per_device_port;
ALTER TABLE meraki.switchport RENAME COLUMN device_serial TO serial;
CREATE INDEX ix_switchport_pk_active ON meraki.switchport (serial, port_id, active_to);

-- ------------------------------------------------------------------
-- uplink_usage: rename columns, drop last_day, fix primary key
-- ------------------------------------------------------------------

ALTER TABLE meraki.uplink_usage DROP CONSTRAINT uplink_usage_pk;
ALTER TABLE meraki.uplink_usage RENAME COLUMN device_serial TO serial;
ALTER TABLE meraki.uplink_usage RENAME COLUMN updated_at TO last_seen;
ALTER TABLE meraki.uplink_usage DROP COLUMN last_day;
ALTER TABLE meraki.uplink_usage ADD CONSTRAINT pk_uplink_usage
    PRIMARY KEY (network_id, serial, interface, month, year);

-- ------------------------------------------------------------------
-- vlan: rename id -> vlan_id (text -> integer), add network_id
-- ------------------------------------------------------------------

ALTER TABLE meraki.vlan DROP CONSTRAINT vlan_pkey;
DROP INDEX meraki.vlan_one_active_per_id;
ALTER TABLE meraki.vlan RENAME COLUMN id TO vlan_id;
ALTER TABLE meraki.vlan ALTER COLUMN vlan_id TYPE integer USING vlan_id::integer;
ALTER TABLE meraki.vlan ADD COLUMN network_id VARCHAR;
CREATE INDEX ix_vlan_pk_active ON meraki.vlan (network_id, vlan_id, active_to);

-- ------------------------------------------------------------------
-- Advance Alembic version
-- ------------------------------------------------------------------

UPDATE meraki.alembic_version
SET version_num = '0003'
WHERE version_num = '0002';

COMMIT;
