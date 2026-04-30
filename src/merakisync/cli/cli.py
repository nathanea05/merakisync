import argparse
import logging

from merakisync.cli.init import init
from merakisync.config import MissingConfigError
from merakisync.dashboard import get_dashboard
from merakisync.db.engine import get_engine

from merakisync import Organization, Network, Device, DhcpServerPolicy

parser=argparse.ArgumentParser("Sync Meraki Network Configurations to a PostgreSQL Database")
parser.add_argument("subcommand", nargs="?")

# Options
parser.add_argument("-s", "--suppress-logging", help="Suppresses Logging")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    try:
        args = parser.parse_args()
        if args.suppress_logging:
            logging.disable(logging.CRITICAL)

        if args.subcommand == "init":
            init()
            return

        if args.subcommand == "migrate":
            print("Please don't do that")
            return

        # Test the configuration
        try:
            dashboard = get_dashboard()
            engine = get_engine()
            conn = engine.connect()
        except MissingConfigError as e:
            logging.error(e)
            return


        logging.info("Syncing Organizations")
        orgs = Organization.sync()
        if not orgs:
            logging.info("Found no orgs")
            return
        logging.info(f"Synced {len(orgs)} Organization(s)")

        for org in orgs:
            logging.info(f"Syncing Networks for Organzation '{org.name}'")
            networks = Network.sync(org.id)
            if not networks:
                logging.error(f"Found no networks at org '{org.name}'")
                continue

            logging.info(f"Found and synced {len(networks)} Network(s)")

            for network in networks:

                if "switch" in network.product_types:
                    DhcpServerPolicy.sync(network.id)
                    logging.info(f"Synced DHCP Server Policy at network '{network.name}'")


        return 0

    

    except KeyboardInterrupt:
        print("")
        quit()

    
if __name__ == "__main__":
    main()

