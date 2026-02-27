from meraki_sync.config import Configuration, prompt_api_key, prompt_database, write_config, get_config, MissingConfigError, get_save_path, ConfigWriteError
from meraki_sync.meraki.dashboard import validate_api_key, MerakiConnectionError
from meraki_sync.db.connection import validate_connection, DatabaseConnectionError
from meraki_sync.utils import confirm

def init():
    # Check if there's an existing config
    save_path = get_save_path()
    try:
        get_config()
        config_exists = True
    except MissingConfigError:
        config_exists = False

    # Confirm Overwrite
    if config_exists: 
        print(f"Found an existing configuration at {save_path}")
        if not confirm("Continue anyway?", default=True):
            return
        print("")


    # Meraki API Key
    print("=== Meraki Configuration ===")
    while True:
        api_key = prompt_api_key()
        try:
            print("Validating API key...")
            validate_api_key(api_key)
            print("✅ Meraki API key validated.")
        except MerakiConnectionError as e:
            print(f"❌ {e}")
            continue
        break
    print("")

    # Database
    print("=== Database Configuration ===")
    while True:
        db_config = prompt_database()
        database_validated = False
        try:
            print("Validating database connection...")
            validate_connection(db_config.get_dsn())
            print("✅ Database connection successful.")
            database_validated = True
        except DatabaseConnectionError as e:
            print(f"❌ Unable to connect to Postgres at {db_config.host}:{db_config.port}")
            print(" Is the server running and accepting TCP connections?")
            if confirm("Continue with these settings despite failed validation?", default=False):
                print("⚠️  Warning: Configuration will be saved without successful validation.")
                break
            else:
                print("")
                print("=== Re-enter Database Configuration ===")
                continue
        break
    print("")

    # Database Migrations
    if database_validated:
        print("=== Database Migration ===")
        if confirm("Apply database migrations now?", default=True):
            print("Coming soon!")
        else:
            print("⚠️  Warning: Database schema has not been verified. Run `merakisync migrate`.")
        print("")


    conf = Configuration.from_parts(api_key=api_key, db=db_config)
    save_path = get_save_path()
    print("✅ Configuration Complete.") 
    print("")
    print("Settings will be saved to:")
    print(save_path)
    if confirm("Save configuration?", default=True):
        write_config(path=save_path, conf=conf)


