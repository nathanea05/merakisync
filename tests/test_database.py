"""Tests for merakisync.database: get_engine, get_session, validate_connection."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from merakisync.database import get_engine, get_session, validate_connection
from merakisync.exceptions import DatabaseConnectionError


class TestGetEngine:
    def setup_method(self):
        get_engine.cache_clear()

    def test_returns_engine_from_dsn(self):
        dsn = "postgresql+psycopg2://user:pass@localhost/db"
        with patch("merakisync.database.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            engine = get_engine(dsn)
        mock_create.assert_called_once()
        assert engine is mock_engine

    def test_reads_dsn_from_config_when_none(self):
        mock_config = MagicMock()
        mock_config.db.get_dsn.return_value = "postgresql+psycopg2://u:p@h/db"
        with patch("merakisync.database.create_engine") as mock_create:
            mock_create.return_value = MagicMock()
            with patch("merakisync.config.get_config", return_value=mock_config):
                get_engine()
        mock_create.assert_called_once()

    def test_none_db_in_config_raises_missing_config_error(self):
        from merakisync.config import Configuration
        from merakisync.exceptions import MissingConfigError
        partial = Configuration(meraki_api_key="some-key", db=None)
        with patch("merakisync.config.get_config", return_value=partial):
            with pytest.raises(MissingConfigError, match="Database"):
                get_engine()

    def test_same_dsn_returns_cached_engine(self):
        dsn = "postgresql+psycopg2://user:pass@localhost/db"
        with patch("merakisync.database.create_engine") as mock_create:
            mock_create.return_value = MagicMock()
            e1 = get_engine(dsn)
            e2 = get_engine(dsn)
        assert e1 is e2
        assert mock_create.call_count == 1

    def test_pool_pre_ping_enabled(self):
        dsn = "postgresql+psycopg2://user:pass@localhost/db"
        with patch("merakisync.database.create_engine") as mock_create:
            mock_create.return_value = MagicMock()
            get_engine(dsn)
        kw = mock_create.call_args.kwargs
        assert kw.get("pool_pre_ping") is True


class TestGetSession:
    def test_yields_session_and_commits(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        mock_engine = MagicMock()
        with patch("merakisync.database._get_session_factory", return_value=mock_factory):
            with get_session(engine=mock_engine) as session:
                assert session is mock_session
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_rollback_on_exception(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        mock_engine = MagicMock()
        with patch("merakisync.database._get_session_factory", return_value=mock_factory):
            with pytest.raises(ValueError):
                with get_session(engine=mock_engine):
                    raise ValueError("oops")
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestValidateConnection:
    def test_success_when_query_works(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        with patch("merakisync.database.get_engine", return_value=mock_engine):
            validate_connection("postgresql+psycopg2://u:p@h/db")  # should not raise

    def test_raises_database_connection_error_on_failure(self):
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("connection refused")
        with patch("merakisync.database.get_engine", return_value=mock_engine):
            with pytest.raises(DatabaseConnectionError):
                validate_connection("postgresql+psycopg2://u:p@h/db")
