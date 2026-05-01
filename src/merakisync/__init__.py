# SPDX-FileCopyrightText: 2026-present Nathan Anderson <nathanea05@gmail.com>
#
# SPDX-License-Identifier: MIT

from merakisync.__about__ import __version__

# Public API surface — import only stable, non-circular symbols at package level.
# Infrastructure helpers
from merakisync.config import get_config
from merakisync.dashboard import get_dashboard
from merakisync.database import get_engine, get_session

# Models
from merakisync.models.organization import Organization
from merakisync.models.network import Network
from merakisync.models.device import Device
from merakisync.models.switchport import Switchport
from merakisync.models.uplink import Uplink
from merakisync.models.uplink_usage import UplinkUsage
from merakisync.models.dhcp_server_policy import DhcpServerPolicy
from merakisync.models.alert import Alert
from merakisync.models.l3_firewall_rule import L3FirewallRule

# Exceptions
from merakisync.exceptions import (
    MissingConfigError,
    ConfigWriteError,
    MerakiConnectionError,
    DatabaseConnectionError,
    UpsertError,
)

__all__ = [
    "__version__",
    # Infrastructure
    "get_config",
    "get_dashboard",
    "get_engine",
    "get_session",
    # Models
    "Organization",
    "Network",
    "Device",
    "Switchport",
    "Uplink",
    "UplinkUsage",
    "DhcpServerPolicy",
    "Alert",
    "L3FirewallRule",
    # Exceptions
    "MissingConfigError",
    "ConfigWriteError",
    "MerakiConnectionError",
    "DatabaseConnectionError",
    "UpsertError",
]
