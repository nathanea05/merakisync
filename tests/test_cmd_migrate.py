"""Tests for cmd_migrate.run()."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from merakisync.cli.cmd_migrate import run


class TestRunMigrate:
    def _mock_alembic(self):
        mock_command = MagicMock()
        mock_config_cls = MagicMock()
        mock_config_instance = MagicMock()
        mock_config_cls.return_value = mock_config_instance
        return mock_command, mock_config_cls, mock_config_instance

    def test_upgrade_called_with_revision(self):
        with patch("alembic.command.upgrade") as mock_upgrade:
            with patch("alembic.config.Config"):
                with patch("importlib.resources.files"):
                    run(revision="head")
        mock_upgrade.assert_called_once()
        _, rev = mock_upgrade.call_args.args
        assert rev == "head"

    def test_upgrade_called_with_custom_revision(self):
        with patch("alembic.command.upgrade") as mock_upgrade:
            with patch("alembic.config.Config"):
                with patch("importlib.resources.files"):
                    run(revision="0005")
        _, rev = mock_upgrade.call_args.args
        assert rev == "0005"

    def test_failure_exits_with_code_1(self):
        with patch("alembic.command.upgrade", side_effect=Exception("migration error")):
            with pytest.raises(SystemExit) as exc_info:
                run()
        assert exc_info.value.code == 1
