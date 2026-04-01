from meraki_sync.meraki.models.organization import Organization
from meraki_sync import get_dashboard

def get_organizations() -> list[Organization]:
    dashboard = get_dashboard()
    raw_orgs = dashboard.organizations.getOrganizations()
    orgs = []
    for raw_org in raw_orgs:
        org = Organization.from_dashboard(raw_org)
        orgs.append(org)
    if not orgs:
        raise LookupError("No orgs found using the configured API Key.")
    return orgs
