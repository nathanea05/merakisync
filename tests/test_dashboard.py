"""Tests for merakisync.dashboard: create_dashboard, get_dashboard,
validate_api_key, reset_dashboard_cache, and the API call counter."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from merakisync.dashboard import (
    DashboardDefaults,
    _ApiCallCounter,
    create_dashboard,
    get_api_call_count,
    reset_api_call_count,
    reset_dashboard_cache,
    validate_api_key,
)
from merakisync.exceptions import MerakiConnectionError


class TestDashboardDefaults:
    def test_defaults_are_sane(self):
        d = DashboardDefaults()
        assert d.suppress_logging is False
        assert d.inherit_logging_config is True
        assert d.print_console is False
        assert d.output_log is False
        assert d.wait_on_rate_limit is True
        assert d.maximum_retries == 20


class TestCreateDashboard:
    def test_empty_api_key_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            create_dashboard("")

    def test_whitespace_only_key_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            create_dashboard("   ")

    def test_valid_key_returns_dashboard(self):
        with patch("meraki.DashboardAPI") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = create_dashboard("abc123")
        mock_cls.assert_called_once()
        assert result is mock_cls.return_value

    def test_key_is_stripped(self):
        with patch("meraki.DashboardAPI") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_dashboard("  abc123  ")
        call_kw = mock_cls.call_args.kwargs
        assert call_kw["api_key"] == "abc123"

    def test_defaults_applied(self):
        with patch("meraki.DashboardAPI") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_dashboard("abc123")
        kw = mock_cls.call_args.kwargs
        assert kw["suppress_logging"] is False
        assert kw["inherit_logging_config"] is True
        assert kw["print_console"] is False
        assert kw["wait_on_rate_limit"] is True
        assert kw["maximum_retries"] == 20


class TestValidateApiKey:
    def test_valid_key_succeeds(self):
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizations.return_value = [{"id": "org1"}]
        with patch("merakisync.dashboard.create_dashboard", return_value=mock_dash):
            validate_api_key("abc123")  # should not raise

    def test_invalid_key_raises_connection_error(self):
        from meraki.exceptions import APIError
        mock_dash = MagicMock()
        mock_dash.organizations.getOrganizations.side_effect = APIError(
            MagicMock(), MagicMock()
        )
        with patch("merakisync.dashboard.create_dashboard", return_value=mock_dash):
            with pytest.raises(MerakiConnectionError):
                validate_api_key("bad_key")


class TestGetDashboard:
    def setup_method(self):
        reset_dashboard_cache()

    def test_returns_dashboard_from_config(self):
        mock_config = MagicMock()
        mock_config.meraki_api_key = "test_key"
        mock_dash = MagicMock()
        with patch("merakisync.dashboard.get_config", return_value=mock_config):
            with patch("merakisync.dashboard.create_dashboard", return_value=mock_dash):
                from merakisync.dashboard import get_dashboard
                result = get_dashboard()
        assert result is mock_dash

    def test_explicit_key_bypasses_config(self):
        mock_dash = MagicMock()
        with patch("merakisync.dashboard.create_dashboard", return_value=mock_dash):
            from merakisync.dashboard import get_dashboard
            result = get_dashboard(api_key="direct_key")
        assert result is mock_dash

    def test_none_api_key_in_config_raises_missing_config_error(self):
        from merakisync.config import Configuration
        from merakisync.exceptions import MissingConfigError
        partial = Configuration(meraki_api_key=None, db=None)
        with patch("merakisync.dashboard.get_config", return_value=partial):
            from merakisync.dashboard import get_dashboard
            with pytest.raises(MissingConfigError, match="Meraki API key"):
                get_dashboard()


class TestResetDashboardCache:
    def test_reset_clears_cache(self):
        mock_dash = MagicMock()
        with patch("merakisync.dashboard.create_dashboard", return_value=mock_dash):
            from merakisync.dashboard import get_dashboard, _get_cached_dashboard
            get_dashboard(api_key="key1")
            info_before = _get_cached_dashboard.cache_info()
            reset_dashboard_cache()
            info_after = _get_cached_dashboard.cache_info()
        assert info_after.currsize == 0


class TestApiCallCounter:
    def setup_method(self):
        reset_api_call_count()

    def test_initial_count_is_zero(self):
        assert get_api_call_count() == 0

    def test_reset_returns_to_zero(self):
        counter = _ApiCallCounter()
        counter.count = 5
        reset_api_call_count()
        assert get_api_call_count() == 0

    def test_http_method_records_are_counted(self):
        counter = _ApiCallCounter()
        for method in ("GET ", "POST ", "PUT ", "DELETE ", "PATCH "):
            record = logging.LogRecord(
                name="meraki", level=logging.INFO,
                pathname="", lineno=0,
                msg=f"{method}https://api.meraki.com/test",
                args=(), exc_info=None,
            )
            counter.emit(record)
        assert counter.count == 5

    def test_non_http_records_are_not_counted(self):
        counter = _ApiCallCounter()
        for msg in ("meraki, getOrganizations - 200 OK", "Session initialized", ""):
            record = logging.LogRecord(
                name="meraki", level=logging.INFO,
                pathname="", lineno=0,
                msg=msg, args=(), exc_info=None,
            )
            counter.emit(record)
        assert counter.count == 0
