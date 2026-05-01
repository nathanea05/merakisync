from __future__ import annotations

import argparse
import sys

from merakisync.cli.cmd_sync import SyncFlags


def _add_log_flags(p: argparse.ArgumentParser) -> None:
    """Add --verbose/--quiet to a subparser without overriding the parent value."""
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS,
        help="Enable debug logging.",
    )
    g.add_argument(
        "-q", "--quiet", action="store_true", default=argparse.SUPPRESS,
        help="Suppress all output below WARNING.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merakisync",
        description="Sync Meraki Dashboard data into PostgreSQL.",
    )

    # Global log-level flags — also added to each subcommand below so they
    # can appear either before or after the subcommand name.
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    log_group.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress all output below WARNING."
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # init
    init_parser = subparsers.add_parser(
        "init",
        help="Configure the Meraki API key and database connection.",
    )
    _add_log_flags(init_parser)

    # migrate
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Apply database migrations (Alembic upgrade head).",
    )
    migrate_parser.add_argument(
        "--revision",
        default="head",
        metavar="REV",
        help="Alembic revision target (default: head).",
    )
    _add_log_flags(migrate_parser)

    # sync
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync Meraki data into the database.",
    )
    _add_log_flags(sync_parser)
    sync_parser.add_argument(
        "-o", "--organizations", action="store_true", help="Sync organizations."
    )
    sync_parser.add_argument(
        "-n", "--networks", action="store_true", help="Sync networks."
    )
    sync_parser.add_argument(
        "-d", "--devices", action="store_true", help="Sync devices."
    )
    sync_parser.add_argument(
        "--switchports", action="store_true", help="Sync switch port configurations."
    )
    sync_parser.add_argument(
        "--uplinks", action="store_true", help="Sync uplink statuses."
    )
    sync_parser.add_argument(
        "--uplink-usage", action="store_true", dest="uplink_usage",
        help="Sync uplink bandwidth usage (current month)."
    )
    sync_parser.add_argument(
        "--dhcp-server-policy", action="store_true", dest="dhcp_server_policy",
        help="Sync switch DHCP server policies."
    )
    sync_parser.add_argument(
        "--alerts", action="store_true", help="Sync assurance alerts."
    )
    sync_parser.add_argument(
        "--l3-firewall-rules", action="store_true", dest="l3_firewall_rules",
        help="Sync MX L3 firewall rules."
    )
    sync_parser.add_argument(
        "--vlans", action="store_true", help="Sync MX appliance VLANs."
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Configure logging before doing anything else
    from merakisync.logging import configure_logging
    configure_logging(verbose=getattr(args, "verbose", False),
                      quiet=getattr(args, "quiet", False))

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        from merakisync.cli.cmd_init import run
        run()
        return

    if args.command == "migrate":
        from merakisync.cli.cmd_migrate import run
        run(revision=args.revision)
        return

    if args.command == "sync":
        # Require a valid config before attempting any sync
        from merakisync.exceptions import MissingConfigError
        import logging
        log = logging.getLogger(__name__)
        try:
            from merakisync.config import get_config
            get_config()
        except MissingConfigError as exc:
            log.error("%s", exc)
            sys.exit(1)

        from merakisync.cli.cmd_sync import run
        flags = SyncFlags(
            organizations=args.organizations,
            networks=args.networks,
            devices=args.devices,
            switchports=args.switchports,
            uplinks=args.uplinks,
            uplink_usage=args.uplink_usage,
            dhcp_server_policy=args.dhcp_server_policy,
            alerts=args.alerts,
            l3_firewall_rules=args.l3_firewall_rules,
            vlans=args.vlans,
        )
        run(flags)
        return


if __name__ == "__main__":
    main()
