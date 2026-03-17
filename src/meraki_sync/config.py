try:
    import tomllib
except:
    import tomli as tomllib
import os
from pathlib import Path
from dataclasses import dataclass
from meraki_sync.utils import prompt
from urllib.parse import quote_plus

from sqlalchemy.engine import URL

class MissingConfigError(Exception):
    """Raised when the config settings are retrieved but not found"""

class ConfigWriteError(RuntimeError):
    """Raised when a config fails to write, usually due to permission or os errors"""

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
        base = f"postgresql://{usr}:{passwd}@{self.host}:{self.port}/{self.name}"
        return base

    def get_sql_alchemy_url(self) -> URL:
        return URL.create(
                drivername="postgresql+psycopg",
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
    def from_parts(cls, api_key: str, db: DbConfig) -> "Configuration":
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("Meraki API key cannot be empty")
        return cls(meraki_api_key=api_key, db=db)

    @classmethod
    def from_toml(cls, data) -> "Configuration":
        api_key = data["meraki"]["api_key"]
        db_host = data["database"]["host"]
        db_port = data["database"]["port"]
        db_name = data["database"]["name"]
        db_user = data["database"]["user"]
        db_password = data["database"]["password"]
        if not api_key:
            raise ValueError("Meraki API Key cannot be empty")
        db = DbConfig(
                host=db_host,
                port=db_port,
                name=db_name,
                user=db_user,
                password=db_password,
                )
        return cls(meraki_api_key=api_key, db=db)


# Read user input
def prompt_api_key() -> str:
    """Prompt the User to Enter Their Meraki API Key"""
    api_key = prompt("Meraki API Key (input hidden) [required]: ", hidden=True, required=True)
    return api_key


def prompt_database() -> DbConfig:
    host = prompt("Postgres host/IP [localhost]: ") or "localhost"
    port = prompt("Postgres port [5432]: ", expect="int") or 5432
    name = prompt("Database name [meraki]: ") or "meraki"
    user = prompt("Database username [merakisync]: ") or "merakisync"
    password = prompt("Database password (input hidden) [required]: ", hidden=True, required=True)
    
    return DbConfig(
            host=host,
            port=port,
            name=name,
            user=user,
            password=password
            )


# Write to file
def get_save_path() -> Path:
    # Prefer /etc if root, else user config
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return Path("/etc/meraki-sync/config.toml")
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "meraki-sync" / "config.toml"
    return Path.home() / ".config" / "meraki-sync" / "config.toml"


def write_config(path: Path, *, conf: Configuration) -> None:
    """
    Writes the config to ~/.config/merakisync/config.toml if run as a standard user.
    Writes to etc/merakisync/config.toml if run with sudo.

    Raises ConfigWriteError on failure.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "[meraki]\n"
            f'api_key = "{conf.meraki_api_key}"\n\n'
            "[database]\n"
            f'host = "{conf.db.host}"\n'
            f'port = "{conf.db.port}"\n'
            f'name = "{conf.db.name}"\n'       
            f'user = "{conf.db.user}"\n'       
            f'password = "{conf.db.password}"\n'       
        )
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
    except PermissionError as e:
        raise ConfigWriteError(
                f"Permission denied writing config to {path}. Try running with sudo."
                ) from e

    except OSError as e:
        raise ConfigWriteError(
                f"Failed to write config to {path}: {e}"
                ) from e

    if not path.exists():
        raise ConfigWriteError(
                f"Failed to write config to {path}: Path does not exist"
                )


# Read from file
def get_config() -> Configuration:
    """Attempts to read the config file and return details as a dict. Raises MissingConfigError if config file or details are missing."""
    path = get_save_path()

    # Ensure config file exists
    if not path.exists():
        raise MissingConfigError("Mission configuration. Try running `merakisync init`")

    # Read Config and return
    with open(path, "rb") as f:
        data = tomllib.load(f)
        conf = Configuration.from_toml(data)
    return conf
