"""Tests for merakisync.logging.configure_logging."""
from __future__ import annotations

import logging
import os
from unittest.mock import patch

from merakisync.logging import configure_logging


class TestConfigureLogging:
    def teardown_method(self):
        # Reset root logger after each test so tests don't pollute each other
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_default_level_is_info(self):
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_verbose_sets_debug(self):
        configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_quiet_sets_warning(self):
        configure_logging(quiet=True)
        assert logging.getLogger().level == logging.WARNING

    def test_quiet_takes_precedence_over_verbose(self):
        # quiet is checked first in the implementation
        configure_logging(quiet=True, verbose=True)
        assert logging.getLogger().level == logging.WARNING

    def test_env_var_sets_level(self):
        with patch.dict(os.environ, {"MERAKISYNC_LOG_LEVEL": "DEBUG"}):
            configure_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_env_var_warning(self):
        with patch.dict(os.environ, {"MERAKISYNC_LOG_LEVEL": "WARNING"}):
            configure_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_invalid_env_var_falls_back_to_info(self):
        with patch.dict(os.environ, {"MERAKISYNC_LOG_LEVEL": "NOTAREAL"}):
            configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_handler_added_to_root(self):
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_existing_handlers_cleared(self):
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        configure_logging()
        assert len(root.handlers) == 1

    def test_sqlalchemy_quieted_at_info(self):
        configure_logging()
        assert logging.getLogger("sqlalchemy").level == logging.WARNING

    def test_sqlalchemy_not_explicitly_set_at_debug(self):
        # Reset sqlalchemy logger first so we start from a known state
        logging.getLogger("sqlalchemy").setLevel(logging.NOTSET)
        configure_logging(verbose=True)
        # At DEBUG level the code does NOT call setLevel(WARNING) on sqlalchemy —
        # the logger stays at NOTSET (inherited from root).
        assert logging.getLogger("sqlalchemy").level == logging.NOTSET

    def test_formatter_includes_asctime(self):
        configure_logging()
        handler = logging.getLogger().handlers[0]
        assert handler.formatter is not None
        assert "%(asctime)s" in handler.formatter._fmt
