"""Tests for merakisync.dashboard: create_dashboard, get_dashboard,
validate_api_key, and reset_dashboard_cache."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from merakisync.dashboard import (
    DashboardDefaults,
    create_dashboard,
    reset_dashboard_cache,
    validate_api_key,
)
from merakisync.exceptions import MerakiConnectionError


class TestDashboardDefaults:
    def test_defaults_are_sane(self):
        d = DashboardDefaults()
        assert d.suppress_logging is True
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
        assert kw["suppress_logging"] is True
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
