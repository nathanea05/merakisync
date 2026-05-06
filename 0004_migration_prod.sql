-- Migration 0004 for production (pacs_engineering)
-- Run as the `meraki` role or a superuser.
--
-- The ssid table already exists in production, so no CREATE TABLE is needed.
-- This script only creates the missing query index and advances the Alembic stamp.

SET search_path TO meraki, public;

CREATE INDEX IF NOT EXISTS ix_ssid_pk_active
    ON meraki.ssid (network_id, number, active_to);

-- Grant DML to the merakisync application user
GRANT SELECT, INSERT, UPDATE, DELETE ON meraki.ssid TO merakisync;

-- Advance Alembic version
UPDATE meraki.alembic_version
    SET version_num = '0004'
    WHERE version_num = '0003';
