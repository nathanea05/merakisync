from __future__ import annotations

from meraki_sync.db.table_factory import build_table_from_model
from meraki_sync.meraki.models.organization import Organization
from meraki_sync.meraki.models.network import Network


organization = build_table_from_model(Organization)
network = build_table_from_model(Network)
