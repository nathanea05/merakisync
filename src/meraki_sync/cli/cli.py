import argparse
from meraki_sync.cli.init import init
from meraki_sync.config import MissingConfigError
from meraki_sync.meraki.dashboard import get_dashboard
from meraki_sync.db.connection import get_conn
from meraki_sync.db.migrate import upgrade_head

parser=argparse.ArgumentParser("Sync Meraki Network Configurations to a PostgreSQL Database")
parser.add_argument("subcommand", nargs="?")


def main() -> int:
    try:
        args = parser.parse_args()

        if args.subcommand == "init":
            init()
            return 0

        if args.subcommand == "migrate":
            upgrade_head()
            print("✅ Database migrated to latest schema.")
            return 0

        try:
            dashboard = get_dashboard()
            with get_conn() as conn:
                with conn.cursor() as cur:
                    print(cur)
        except MissingConfigError as e:
            print(e)
            return 0
        print(dashboard)
    except KeyboardInterrupt:
        print("")
        quit()

    
if __name__ == "__main__":
    main()

