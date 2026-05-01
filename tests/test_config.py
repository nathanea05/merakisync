"""Tests for configuration loading, env var overlay, and path resolution."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from merakisync.config import (
    Configuration,
    DbConfig,
    get_config,
    get_save_path,
    write_config,
)
from merakisync.exceptions import MissingConfigError


MINIMAL_TOML = """\
[meraki]
api_key = "test-api-key"

[database]
host = "localhost"
port = 5432
name = "meraki"
user = "merakisync"
password = "secret"
"""


# ---------------------------------------------------------------------------
# DbConfig
# ---------------------------------------------------------------------------

class TestDbConfig:
    def test_get_dsn_format(self):
        db = DbConfig(host="db.example.com", port=5432, name="mydb", user="u", password="p")
        dsn = db.get_dsn()
        assert dsn.startswith("postgresql://")
        assert "db.example.com" in dsn
        assert "5432" in dsn
        assert "mydb" in dsn

    def test_get_dsn_url_encodes_password(self):
        db = DbConfig(host="localhost", port=5432, name="db", user="u", password="p@$$")
        dsn = db.get_dsn()
        assert "p%40%24%24" in dsn  # URL-encoded

    def test_sqlalchemy_url_driver(self):
        db = DbConfig(host="localhost", port=5432, name="db", user="u", password="p")
        url = db.get_sqlalchemy_url()
        assert url.drivername == "postgresql+psycopg2"


# ---------------------------------------------------------------------------
# Configuration.from_toml
# ---------------------------------------------------------------------------

class TestConfigurationFromToml:
    def test_parses_correctly(self):
        import tomllib
        data = tomllib.loads(MINIMAL_TOML)
        conf = Configuration.from_toml(data)
        assert conf.meraki_api_key == "test-api-key"
        assert conf.db.host == "localhost"
        assert conf.db.port == 5432
        assert conf.db.name == "meraki"

    def test_empty_api_key_raises(self):
        import tomllib
        bad = MINIMAL_TOML.replace('api_key = "test-api-key"', 'api_key = ""')
        data = tomllib.loads(bad)
        with pytest.raises(ValueError, match="API key"):
            Configuration.from_toml(data)


# ---------------------------------------------------------------------------
# get_save_path
# ---------------------------------------------------------------------------

class TestGetSavePath:
    def test_non_root_uses_home(self):
        with patch("os.geteuid", return_value=1000):
            path = get_save_path()
        assert "merakisync" in str(path)
        assert str(path).endswith("config.toml")

    def test_xdg_config_home_respected(self):
        with patch("os.geteuid", return_value=1000), \
             patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
            path = get_save_path()
        assert str(path).startswith("/custom/config")


# ---------------------------------------------------------------------------
# get_config with env var overlay
# ---------------------------------------------------------------------------

class TestGetConfigEnvOverlay:
    def test_env_overrides_file(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(MINIMAL_TOML, encoding="utf-8")
        cfg_file.chmod(0o600)

        env = {"MERAKI_API_KEY": "from-env-key"}
        with patch("merakisync.config.get_save_path", return_value=cfg_file), \
             patch.dict(os.environ, env):
            conf = get_config()

        assert conf.meraki_api_key == "from-env-key"
        assert conf.db.host == "localhost"  # still from file

    def test_db_host_env_override(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(MINIMAL_TOML, encoding="utf-8")
        cfg_file.chmod(0o600)

        env = {"MERAKISYNC_DB_HOST": "remotehost"}
        with patch("merakisync.config.get_save_path", return_value=cfg_file), \
             patch.dict(os.environ, env):
            conf = get_config()

        assert conf.db.host == "remotehost"

    def test_no_file_no_env_raises(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.toml"
        clean_env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("MERAKISYNC") and k != "MERAKI_API_KEY"
        }
        with patch("merakisync.config.get_save_path", return_value=missing), \
             patch.dict(os.environ, clean_env, clear=True):
            with pytest.raises(MissingConfigError):
                get_config()

    def test_all_env_no_file(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.toml"
        env = {
            "MERAKI_API_KEY": "env-api-key",
            "MERAKISYNC_DB_HOST": "envhost",
            "MERAKISYNC_DB_PORT": "5433",
            "MERAKISYNC_DB_NAME": "envdb",
            "MERAKISYNC_DB_USER": "envuser",
            "MERAKISYNC_DB_PASSWORD": "envpass",
        }
        with patch("merakisync.config.get_save_path", return_value=missing), \
             patch.dict(os.environ, env, clear=True):
            conf = get_config()

        assert conf.meraki_api_key == "env-api-key"
        assert conf.db.host == "envhost"
        assert conf.db.port == 5433


# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------

class TestWriteConfig:
    def test_writes_and_sets_permissions(self, tmp_path: Path):
        cfg_file = tmp_path / "sub" / "config.toml"
        db = DbConfig(host="localhost", port=5432, name="db", user="u", password="p")
        conf = Configuration(meraki_api_key="key123", db=db)
        write_config(cfg_file, conf=conf)

        assert cfg_file.exists()
        assert oct(cfg_file.stat().st_mode)[-3:] == "600"
        content = cfg_file.read_text()
        assert "key123" in content
        assert "localhost" in content
        # port should be an integer in TOML, not quoted
        assert "port = 5432" in content
