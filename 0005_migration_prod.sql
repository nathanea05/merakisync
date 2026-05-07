-- Migration 0005 — production manual script
-- Run as the meraki role (table owner) when merakisync lacks ALTER TABLE privilege.
--
-- Drops switchport columns that are only available from the per-device endpoint
-- and cannot be maintained by the org-level sync.

BEGIN;

ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS isolation_enabled;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS port_schedule_id;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS udld;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS access_policy_number;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS mac_allow_list;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS storm_control_enabled;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS adaptive_policy_group_id;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS peer_sgt_capable;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS flexible_stacking_enabled;
ALTER TABLE meraki.switchport DROP COLUMN IF EXISTS dai_trusted;

-- Advance Alembic to 0005 so merakisync migrate is a no-op.
UPDATE meraki.alembic_version SET version_num = '0005';

COMMIT;
