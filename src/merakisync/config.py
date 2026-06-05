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
    meraki_api_key: str | None = None
    db: DbConfig | None = None

    @classmethod
    def from_parts(cls, api_key: str | None = None, db: DbConfig | None = None) -> Configuration:
        if api_key is not None:
            api_key = api_key.strip() or None
        return cls(meraki_api_key=api_key, db=db)

    @classmethod
    def from_toml(cls, data: dict) -> Configuration:
        meraki_section = data.get("meraki", {})
        api_key: str | None = meraki_section.get("api_key") or None

        db: DbConfig | None = None
        d = data.get("database")
        if d:
            db = DbConfig(
                host=d["host"],
                port=int(d["port"]),
                name=d["name"],
                user=d["user"],
                password=d["password"],
            )

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

    Returns a Configuration where either or both fields may be None if only
    a partial configuration is present. Callers that require a specific field
    (e.g. the sync command) should check the field and raise with a clear
    message if it is absent.

    Environment variable overrides (all optional):
        MERAKI_API_KEY
        MERAKISYNC_DB_HOST
        MERAKISYNC_DB_PORT
        MERAKISYNC_DB_NAME
        MERAKISYNC_DB_USER
        MERAKISYNC_DB_PASSWORD

    Raises:
        MissingConfigError: only when no config file exists and no relevant
            environment variables are set at all.
    """
    path = get_save_path()

    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        conf = Configuration.from_toml(data)
        api_key: str | None = conf.meraki_api_key
        db: DbConfig | None = conf.db
    else:
        api_key = None
        db = None

    # Overlay env vars over file values
    env_api_key = os.getenv("MERAKI_API_KEY", "").strip()
    if env_api_key:
        api_key = env_api_key

    env_db_host = os.getenv("MERAKISYNC_DB_HOST", "")
    if db is not None:
        db = DbConfig(
            host=os.getenv("MERAKISYNC_DB_HOST", db.host),
            port=int(os.getenv("MERAKISYNC_DB_PORT", str(db.port))),
            name=os.getenv("MERAKISYNC_DB_NAME", db.name),
            user=os.getenv("MERAKISYNC_DB_USER", db.user),
            password=os.getenv("MERAKISYNC_DB_PASSWORD", db.password),
        )
    elif env_db_host:
        # No file DB section — attempt to build entirely from env vars
        port_str = os.getenv("MERAKISYNC_DB_PORT", "5432")
        name = os.getenv("MERAKISYNC_DB_NAME", "")
        user = os.getenv("MERAKISYNC_DB_USER", "")
        password = os.getenv("MERAKISYNC_DB_PASSWORD", "")
        if name and user and password:
            db = DbConfig(host=env_db_host, port=int(port_str), name=name, user=user, password=password)

    if api_key is None and db is None:
        raise MissingConfigError(
            "No configuration found. Run `merakisync init` or set the "
            "MERAKI_API_KEY and MERAKISYNC_DB_* environment variables."
        )

    return Configuration(meraki_api_key=api_key, db=db)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_config(path: Path, *, conf: Configuration) -> None:
    """Write configuration to *path* as TOML with mode 0600.

    Only sections whose corresponding field is not None are written.

    Raises:
        ConfigWriteError: on permission or OS errors.
    """
    sections: list[str] = []

    if conf.meraki_api_key is not None:
        sections.append(
            "[meraki]\n"
            f'api_key = "{conf.meraki_api_key}"\n'
        )

    if conf.db is not None:
        # port is written as an integer (no quotes) so tomllib reads it back as int
        sections.append(
            "[database]\n"
            f'host = "{conf.db.host}"\n'
            f"port = {conf.db.port}\n"
            f'name = "{conf.db.name}"\n'
            f'user = "{conf.db.user}"\n'
            f'password = "{conf.db.password}"\n'
        )

    content = "\n".join(sections)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
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
