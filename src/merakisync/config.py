from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy.engine import URL

from merakisync.exceptions import ConfigWriteError, MissingConfigError
from merakisync.utils.confirm import confirm
from merakisync.utils.prompt import prompt


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    name: str
    user: str
    password: str

    def get_dsn(self) -> str:
        usr = quote_plus(self.user)
        passwd = quote_plus(self.password)
        return f"postgresql://{usr}:{passwd}@{self.host}:{self.port}/{self.name}"

    def get_sqlalchemy_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        )


@dataclass(frozen=True)
class Configuration:
    meraki_api_key: str
    db: DbConfig

    @classmethod
    def from_parts(cls, api_key: str, db: DbConfig) -> Configuration:
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("Meraki API key cannot be empty")
        return cls(meraki_api_key=api_key, db=db)

    @classmethod
    def from_toml(cls, data: dict) -> Configuration:
        api_key = data["meraki"]["api_key"]
        d = data["database"]
        db = DbConfig(
            host=d["host"],
            port=int(d["port"]),
            name=d["name"],
            user=d["user"],
            password=d["password"],
        )
        if not api_key:
            raise ValueError("Meraki API key cannot be empty")
        return cls(meraki_api_key=api_key, db=db)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def get_save_path() -> Path:
    """Return the platform-appropriate config file path."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return Path("/etc/merakisync/config.toml")
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "merakisync" / "config.toml"
    return Path.home() / ".config" / "merakisync" / "config.toml"


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_config() -> Configuration:
    """Load configuration from the TOML file, then overlay any env vars set.

    Environment variable overrides (all optional):
        MERAKI_API_KEY
        MERAKISYNC_DB_HOST
        MERAKISYNC_DB_PORT
        MERAKISYNC_DB_NAME
        MERAKISYNC_DB_USER
        MERAKISYNC_DB_PASSWORD

    Raises:
        MissingConfigError: if the config file is absent and env vars do not
            provide a complete configuration.
    """
    path = get_save_path()

    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        conf = Configuration.from_toml(data)
        api_key: str = conf.meraki_api_key
        db: DbConfig | None = conf.db
    else:
        api_key = ""
        db = None

    # Overlay env vars over file values
    api_key = os.getenv("MERAKI_API_KEY", api_key).strip()

    if db is not None:
        db = DbConfig(
            host=os.getenv("MERAKISYNC_DB_HOST", db.host),
            port=int(os.getenv("MERAKISYNC_DB_PORT", str(db.port))),
            name=os.getenv("MERAKISYNC_DB_NAME", db.name),
            user=os.getenv("MERAKISYNC_DB_USER", db.user),
            password=os.getenv("MERAKISYNC_DB_PASSWORD", db.password),
        )
    else:
        # No file — attempt to build entirely from env vars
        host = os.getenv("MERAKISYNC_DB_HOST", "")
        port_str = os.getenv("MERAKISYNC_DB_PORT", "5432")
        name = os.getenv("MERAKISYNC_DB_NAME", "")
        user = os.getenv("MERAKISYNC_DB_USER", "")
        password = os.getenv("MERAKISYNC_DB_PASSWORD", "")
        if host and name and user and password:
            db = DbConfig(host=host, port=int(port_str), name=name, user=user, password=password)
        else:
            raise MissingConfigError(
                "No configuration found. Run `merakisync init` or set the "
                "MERAKI_API_KEY and MERAKISYNC_DB_* environment variables."
            )

    if not api_key:
        raise MissingConfigError(
            "Meraki API key is missing. Run `merakisync init` or set MERAKI_API_KEY."
        )

    return Configuration(meraki_api_key=api_key, db=db)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_config(path: Path, *, conf: Configuration) -> None:
    """Write configuration to *path* as TOML with mode 0600.

    Raises:
        ConfigWriteError: on permission or OS errors.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # port is written as an integer (no quotes) so tomllib reads it back as int
        content = (
            "[meraki]\n"
            f'api_key = "{conf.meraki_api_key}"\n\n'
            "[database]\n"
            f'host = "{conf.db.host}"\n'
            f"port = {conf.db.port}\n"
            f'name = "{conf.db.name}"\n'
            f'user = "{conf.db.user}"\n'
            f'password = "{conf.db.password}"\n'
        )
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
    except PermissionError as exc:
        raise ConfigWriteError(
            f"Permission denied writing config to {path}. Try running with sudo."
        ) from exc
    except OSError as exc:
        raise ConfigWriteError(f"Failed to write config to {path}: {exc}") from exc

    if not path.exists():
        raise ConfigWriteError(
            f"Config write appeared to succeed but {path} does not exist."
        )


# ---------------------------------------------------------------------------
# Interactive prompts  (used by `merakisync init`)
# ---------------------------------------------------------------------------

def prompt_api_key() -> str:
    return prompt("Meraki API Key (input hidden) [required]: ", hidden=True, required=True)


def prompt_database() -> DbConfig:
    host = prompt("Postgres host/IP [localhost]: ") or "localhost"
    port = prompt("Postgres port [5432]: ", expect="int") or 5432
    name = prompt("Database name [merakisync]: ") or "merakisync"
    user = prompt("Database username [merakisync]: ") or "merakisync"
    password = prompt("Database password (input hidden) [required]: ", hidden=True, required=True)
    return DbConfig(host=host, port=int(port), name=name, user=user, password=password)
