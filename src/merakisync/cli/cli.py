import argparse
from merakisync.cli.init import init
from merakisync.config import MissingConfigError
from merakisync.dashboard import get_dashboard
from merakisync.db.engine import get_engine

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


        return 0

    

    except KeyboardInterrupt:
        print("")
        quit()

    
if __name__ == "__main__":
    main()

