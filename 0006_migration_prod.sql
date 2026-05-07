-- Migration 0006 — production manual script
-- Run as the meraki role (table owner).
--
-- Drops legacy switchport columns that are not part of the merakisync schema
-- and cause every port to appear "changed" on every sync.

BEGIN;

ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS stp_port_fast_trunk;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS link_negotiation_capabilities;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS schedule;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS mac_whitelist_limit;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS adaptive_policy_group;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS profile;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS module;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS mirror;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS dot3az;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS high_speed;

UPDATE meraki.alembic_version SET version_num = '0006';

COMMIT;
