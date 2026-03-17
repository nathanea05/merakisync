from meraki_sync.meraki.dashboard import get_dashboard
from meraki_sync.meraki.models.network import Network
from meraki_sync.meraki.models.organization import Organization

def get_networks(org: dict | Organization | None = None,
                 orgs: list[dict] | list[Organization] | None = None
                 ) -> list[Network]:

    """
    Returns a list of Networks belonging to the provided org(s). 
    If no org is provided, it will return all networks accessible by the configured API key, 
    regardless of organization

    Each organization should be an instance of the Organization class, or the raw dict returned by Meraki
    """
    dashboard = get_dashboard()

    if not orgs:
        orgs = []
    
    if org:
        orgs.append(org)

    
    if not orgs:
        raw_orgs = dashboard.organizations.getOrganizations(total_pages="all")
        for raw_org in raw_orgs:
            org = Organization.from_dashboard(raw_org)
            orgs.append(org)
    else:
        # Convert to Organization class if not already
        sanitized_orgs = []
        for org in orgs:
            if not isinstance(org, Organization):
                sanitized_org = Organization.from_dashboard(org)
                sanitized_orgs.append(sanitized_org)
            else:
                sanitized_orgs.append(org)
        orgs = sanitized_orgs
    
    networks = []

    for org in orgs:
        raw_networks = dashboard.organizations.getOrganizationNetworks(org.id, total_pages="all")
        for raw_network in raw_networks:
            network = Network.from_dashboard(raw_network)
            networks.append(network)

    if networks:
        networks.sort(key=lambda n: n.name) # Sort alphabetically
        return networks
    else:
        raise LookupError(f"Networks not found for Organization {org.name}")
