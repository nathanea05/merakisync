import argparse
from meraki_sync.cli.init import init
from meraki_sync.config import MissingConfigError
from meraki_sync.meraki.dashboard import get_dashboard
from meraki_sync.db.engine import get_engine

parser=argparse.ArgumentParser("Sync Meraki Network Configurations to a PostgreSQL Database")
parser.add_argument("subcommand", nargs="?")


def main() -> int:
    try:
        args = parser.parse_args()

        if args.subcommand == "init":
            init()
            return 0

        if args.subcommand == "migrate":
            print("Please don't do that")
            return 0

        try:
            dashboard = get_dashboard()
            engine = get_engine()
            conn = engine.connect()
        except MissingConfigError as e:
            print(e)
            return 1


        from meraki_sync.sync.organization import sync_organization
        sync_organization()
        return 0

    

    except KeyboardInterrupt:
        print("")
        quit()

    
if __name__ == "__main__":
    main()

