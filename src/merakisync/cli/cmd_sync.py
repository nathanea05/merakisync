from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SyncFlags:
    """Which resource types to sync.  All False means sync everything."""

    organizations: bool = False
    networks: bool = False
    devices: bool = False
    switchports: bool = False
    uplinks: bool = False
    uplink_usage: bool = False
    dhcp_server_policy: bool = False
    alerts: bool = False
    l3_firewall_rules: bool = False
    vlans: bool = False

    @property
    def sync_all(self) -> bool:
        return not any(vars(self).values())


def run(flags: SyncFlags | None = None) -> None:
    """Orchestrate a full or selective sync.

    Sync order respects dependencies:
        Organizations → Networks → Devices → per-network/per-device resources

    Args:
        flags: Controls which resource types are synced.  Pass None or an
               all-False SyncFlags to sync everything.
    """
    if flags is None:
        flags = SyncFlags()

    from merakisync.models.organization import Organization
    from merakisync.models.network import Network
    from merakisync.models.device import Device
    from merakisync.models.switchport import Switchport
    from merakisync.models.uplink import Uplink
    from merakisync.models.uplink_usage import UplinkUsage
    from merakisync.models.dhcp_server_policy import DhcpServerPolicy
    from merakisync.models.alert import Alert
    from merakisync.models.l3_firewall_rule import L3FirewallRule
    from merakisync.models.vlan import Vlan

    do_all = flags.sync_all

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------
    if do_all or flags.organizations:
        logger.info("Syncing organizations...")
        orgs = Organization.sync()
    else:
        # We always need the org list to drive child syncs
        logger.debug("Fetching organizations (not syncing to DB)...")
        orgs = Organization.get(source="meraki")

    if not orgs:
        logger.error("No organizations found. Aborting sync.")
        return

    logger.info("Found %d organization(s).", len(orgs))

    for org in orgs:
        org_id = org.id
        logger.info("Processing org: %s (%s)", org.name, org_id)

        # --------------------------------------------------------------
        # Alerts  (org-level, no network dependency)
        # --------------------------------------------------------------
        if do_all or flags.alerts:
            logger.info("  Syncing alerts for org %s...", org_id)
            Alert.sync(org_id)

        # --------------------------------------------------------------
        # Uplinks  (org-level)
        # --------------------------------------------------------------
        if do_all or flags.uplinks:
            logger.info("  Syncing uplinks for org %s...", org_id)
            Uplink.sync(org_id)

        # --------------------------------------------------------------
        # Uplink usage  (org-level)
        # --------------------------------------------------------------
        if do_all or flags.uplink_usage:
            logger.info("  Syncing uplink usage for org %s...", org_id)
            UplinkUsage.sync(org_id)

        # --------------------------------------------------------------
        # Devices  (org-level)
        # --------------------------------------------------------------
        if do_all or flags.devices:
            logger.info("  Syncing devices for org %s...", org_id)
            Device.sync(org_id)

        # --------------------------------------------------------------
        # Networks → per-network resources
        # --------------------------------------------------------------
        need_networks = do_all or flags.networks or flags.switchports \
            or flags.dhcp_server_policy or flags.l3_firewall_rules or flags.vlans

        if not need_networks:
            continue

        if do_all or flags.networks:
            logger.info("  Syncing networks for org %s...", org_id)
            networks = Network.sync(org_id)
        else:
            networks = Network.get(org_id, source="meraki")

        if not networks:
            logger.warning("  No networks found for org %s.", org_id)
            continue

        logger.info("  Found %d network(s) in org %s.", len(networks), org_id)

        for network in networks:
            net_id = network.id
            product_types = set(network.product_types or [])

            # ----------------------------------------------------------
            # DHCP server policy  (switch networks only)
            # ----------------------------------------------------------
            if (do_all or flags.dhcp_server_policy) and "switch" in product_types:
                logger.debug("    Syncing DHCP server policy for network %s...", net_id)
                DhcpServerPolicy.sync(net_id)

            # ----------------------------------------------------------
            # L3 firewall rules  (appliance networks only)
            # ----------------------------------------------------------
            if (do_all or flags.l3_firewall_rules) and "appliance" in product_types:
                logger.debug("    Syncing L3 firewall rules for network %s...", net_id)
                L3FirewallRule.sync(net_id)

            # ----------------------------------------------------------
            # VLANs  (appliance networks only)
            # ----------------------------------------------------------
            if (do_all or flags.vlans) and "appliance" in product_types:
                logger.info("    Syncing VLANs for network %s...", net_id)
                Vlan.sync(net_id)

        # --------------------------------------------------------------
        # Switchports  (per switch device)
        # --------------------------------------------------------------
        if do_all or flags.switchports:
            logger.info("  Syncing switchports for org %s...", org_id)
            switch_devices = Device.get(
                org_id,
                source="database",
                product_types_include=["switch"],
            )
            if not switch_devices:
                logger.info("  No switch devices found in org %s.", org_id)
            else:
                for device in switch_devices:
                    logger.debug("    Syncing ports for device %s...", device.serial)
                    Switchport.sync(device.serial)

    logger.info("Sync complete.")
