from merakisync.meraki.dashboard import get_dashboard
from merakisync.meraki.models.organization import Organization

def sync_organization():
    dashboard = get_dashboard()
    orgs = dashboard.organizations.getOrganizations()
    for org in orgs:
        res = Organization.from_dashboard(org)
        print(res)
