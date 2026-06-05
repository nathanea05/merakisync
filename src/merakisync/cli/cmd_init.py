from __future__ import annotations

from merakisync.config import (
    Configuration,
    DbConfig,
    get_config,
    get_save_path,
    prompt_api_key,
    prompt_database,
    write_config,
)
from merakisync.dashboard import validate_api_key
from merakisync.database import validate_connection
from merakisync.exceptions import (
    ConfigWriteError,
    DatabaseConnectionError,
    MerakiConnectionError,
    MissingConfigError,
)
from merakisync.utils.confirm import confirm


def run(*, configure_meraki: bool = True, configure_database: bool = True) -> None:
    """Interactive `merakisync init` wizard.

    Args:
        configure_meraki: Prompt for and save the Meraki API key.
        configure_database: Prompt for and save the database connection.
    """
    save_path = get_save_path()

    # Load existing config to preserve whichever section won't be re-configured.
    existing: Configuration | None = None
    try:
        existing = get_config()
        config_exists = True
    except MissingConfigError:
        config_exists = False

    if config_exists:
        print(f"Found an existing configuration at {save_path}")
        if not confirm("Continue anyway?", default=True):
            return
        print("")

    api_key: str | None = existing.meraki_api_key if existing else None
    db_config: DbConfig | None = existing.db if existing else None
    database_validated = False

    # --- Meraki API key --------------------------------------------------
    if configure_meraki:
        print("=== Meraki Configuration ===")
        while True:
            new_api_key = prompt_api_key()
            print("Validating API key...")
            try:
                validate_api_key(new_api_key)
                print("OK  Meraki API key validated.")
                api_key = new_api_key
                break
            except MerakiConnectionError as exc:
                print(f"FAIL  {exc}")
        print("")

    # --- Database --------------------------------------------------------
    if configure_database:
        print("=== Database Configuration ===")
        while True:
            new_db_config = prompt_database()
            print("Validating database connection...")
            try:
                validate_connection(new_db_config.get_dsn())
                print("OK  Database connection successful.")
                db_config = new_db_config
                database_validated = True
                break
            except DatabaseConnectionError:
                print(f"FAIL  Unable to connect to Postgres at {new_db_config.host}:{new_db_config.port}")
                print("      Is the server running and accepting TCP connections?")
                if confirm("Continue with these settings despite failed validation?", default=False):
                    print("WARN  Configuration will be saved without successful validation.")
                    db_config = new_db_config
                    break
                print("")
                print("=== Re-enter Database Configuration ===")
        print("")

    # --- Save ------------------------------------------------------------
    conf = Configuration.from_parts(api_key=api_key, db=db_config)
    print("Configuration complete.")
    print(f"Settings will be saved to: {save_path}")
    config_saved = False
    if confirm("Save configuration?", default=True):
        try:
            write_config(path=save_path, conf=conf)
            print(f"OK  Config saved to {save_path}")
            config_saved = True
        except ConfigWriteError as exc:
            print(f"FAIL  {exc}")
    print("")

    # --- Migrations ------------------------------------------------------
    if config_saved and configure_database and database_validated:
        print("=== Database Migrations ===")
        if confirm("Apply database migrations now?", default=True):
            _run_migrations()
        else:
            print("WARN  Schema not applied. Run `merakisync migrate` before syncing.")
        print("")


def _run_migrations() -> None:
    """Invoke Alembic migrations programmatically."""
    try:
        from merakisync.cli.cmd_migrate import run as migrate_run
        migrate_run()
        print("OK  Migrations applied.")
    except SystemExit:
        print("FAIL  Migration failed.")
        print("      Run `merakisync migrate` manually to retry.")
