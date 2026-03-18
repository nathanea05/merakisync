from meraki_sync import get_dashboard, get_organizations
from meraki_sync.meraki.models.alert import Alert

def get_alerts() -> list[Alert]:
    dashboard = get_dashboard()
    orgs = get_organizations()
    total_alerts = []
    for org in orgs:
        alerts = dashboard.organizations.getOrganizationAssuranceAlerts(
                org.id, total_pages="all"
                )
        for alert in alerts:
            alert["OrgId"] = org.id
            network = alert.get("network")
            alert["networkId"] = network.get("id")
            alert["networkName"] = network.get("name")
            alert_obj = Alert.from_dashboard(alert)
            total_alerts.append(alert_obj)
    return total_alerts
