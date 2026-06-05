"""Tests for the CLI: argument parsing, --version, and SyncFlags.sync_all."""
from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from merakisync.cli.cli import _build_parser, main
from merakisync.cli.cmd_sync import SyncFlags


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------

class TestParser:
    def setup_method(self):
        self.parser = _build_parser()

    def test_version_flag_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            self.parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_version_output(self, capsys):
        with pytest.raises(SystemExit):
            self.parser.parse_args(["--version"])
        out = capsys.readouterr().out
        assert "merakisync" in out

    def test_no_args_command_is_none(self):
        args = self.parser.parse_args([])
        assert args.command is None

    def test_init_subcommand_parsed(self):
        args = self.parser.parse_args(["init"])
        assert args.command == "init"

    def test_init_meraki_flag(self):
        args = self.parser.parse_args(["init", "--meraki"])
        assert args.meraki is True
        assert args.database is False

    def test_init_database_flag(self):
        args = self.parser.parse_args(["init", "--database"])
        assert args.database is True
        assert args.meraki is False

    def test_init_both_flags(self):
        args = self.parser.parse_args(["init", "--meraki", "--database"])
        assert args.meraki is True
        assert args.database is True

    def test_init_no_flags_defaults_false(self):
        args = self.parser.parse_args(["init"])
        assert args.meraki is False
        assert args.database is False

    def test_migrate_default_revision(self):
        args = self.parser.parse_args(["migrate"])
        assert args.command == "migrate"
        assert args.revision == "head"

    def test_migrate_custom_revision(self):
        args = self.parser.parse_args(["migrate", "--revision", "0005"])
        assert args.revision == "0005"

    def test_sync_organizations(self):
        args = self.parser.parse_args(["sync", "--organizations"])
        assert args.organizations is True
        assert args.networks is False

    def test_sync_networks(self):
        args = self.parser.parse_args(["sync", "--networks"])
        assert args.networks is True

    def test_sync_devices(self):
        args = self.parser.parse_args(["sync", "--devices"])
        assert args.devices is True

    def test_sync_switchports(self):
        args = self.parser.parse_args(["sync", "--switchports"])
        assert args.switchports is True

    def test_sync_uplinks(self):
        args = self.parser.parse_args(["sync", "--uplinks"])
        assert args.uplinks is True

    def test_sync_uplink_usage(self):
        args = self.parser.parse_args(["sync", "--uplink-usage"])
        assert args.uplink_usage is True

    def test_sync_dhcp_server_policy(self):
        args = self.parser.parse_args(["sync", "--dhcp-server-policy"])
        assert args.dhcp_server_policy is True

    def test_sync_alerts(self):
        args = self.parser.parse_args(["sync", "--alerts"])
        assert args.alerts is True

    def test_sync_l3_firewall_rules(self):
        args = self.parser.parse_args(["sync", "--l3-firewall-rules"])
        assert args.l3_firewall_rules is True

    def test_sync_vlans(self):
        args = self.parser.parse_args(["sync", "--vlans"])
        assert args.vlans is True

    def test_sync_ssids(self):
        args = self.parser.parse_args(["sync", "--ssids"])
        assert args.ssids is True

    def test_verbose_flag(self):
        args = self.parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_quiet_flag(self):
        args = self.parser.parse_args(["--quiet"])
        assert args.quiet is True

    def test_verbose_and_quiet_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            self.parser.parse_args(["--verbose", "--quiet"])

    def test_short_org_flag(self):
        args = self.parser.parse_args(["sync", "-o"])
        assert args.organizations is True

    def test_short_network_flag(self):
        args = self.parser.parse_args(["sync", "-n"])
        assert args.networks is True

    def test_short_device_flag(self):
        args = self.parser.parse_args(["sync", "-d"])
        assert args.devices is True


# ---------------------------------------------------------------------------
# SyncFlags
# ---------------------------------------------------------------------------

class TestSyncFlags:
    def test_all_false_means_sync_all(self):
        flags = SyncFlags()
        assert flags.sync_all is True

    def test_any_true_means_not_sync_all(self):
        flags = SyncFlags(organizations=True)
        assert flags.sync_all is False

    def test_multiple_flags(self):
        flags = SyncFlags(networks=True, devices=True)
        assert flags.sync_all is False
        assert flags.networks is True
        assert flags.devices is True
        assert flags.organizations is False


# ---------------------------------------------------------------------------
# main() — dispatch
# ---------------------------------------------------------------------------

class TestMainDispatch:
    def test_no_args_prints_help_and_exits_zero(self):
        with patch("sys.argv", ["merakisync"]):
            with patch("merakisync.logging.configure_logging"):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0

    def test_init_dispatch(self):
        with patch("sys.argv", ["merakisync", "init"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.cli.cmd_init.run") as mock_run:
                    main()
        mock_run.assert_called_once_with(configure_meraki=True, configure_database=True)

    def test_init_meraki_only_dispatch(self):
        with patch("sys.argv", ["merakisync", "init", "--meraki"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.cli.cmd_init.run") as mock_run:
                    main()
        mock_run.assert_called_once_with(configure_meraki=True, configure_database=False)

    def test_init_database_only_dispatch(self):
        with patch("sys.argv", ["merakisync", "init", "--database"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.cli.cmd_init.run") as mock_run:
                    main()
        mock_run.assert_called_once_with(configure_meraki=False, configure_database=True)

    def test_migrate_dispatch(self):
        with patch("sys.argv", ["merakisync", "migrate"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.cli.cmd_migrate.run") as mock_run:
                    main()
        mock_run.assert_called_once_with(revision="head")

    def test_migrate_custom_revision_passed(self):
        with patch("sys.argv", ["merakisync", "migrate", "--revision", "0003"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.cli.cmd_migrate.run") as mock_run:
                    main()
        mock_run.assert_called_once_with(revision="0003")

    def test_sync_dispatch(self):
        mock_config = MagicMock()
        with patch("sys.argv", ["merakisync", "sync"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.config.get_config", return_value=mock_config):
                    with patch("merakisync.cli.cmd_sync.run") as mock_run:
                        main()
        mock_run.assert_called_once()

    def test_sync_missing_config_exits_nonzero(self):
        from merakisync.exceptions import MissingConfigError
        with patch("sys.argv", ["merakisync", "sync"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.config.get_config", side_effect=MissingConfigError("no config")):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
        assert exc_info.value.code == 1

    def test_sync_no_api_key_exits_nonzero(self):
        from merakisync.config import Configuration, DbConfig
        db = DbConfig(host="localhost", port=5432, name="db", user="u", password="p")
        partial = Configuration(meraki_api_key=None, db=db)
        with patch("sys.argv", ["merakisync", "sync"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.config.get_config", return_value=partial):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
        assert exc_info.value.code == 1

    def test_sync_no_db_exits_nonzero(self):
        from merakisync.config import Configuration
        partial = Configuration(meraki_api_key="some-key", db=None)
        with patch("sys.argv", ["merakisync", "sync"]):
            with patch("merakisync.logging.configure_logging"):
                with patch("merakisync.config.get_config", return_value=partial):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
        assert exc_info.value.code == 1
