# merakisync

Sync Meraki Dashboard data into PostgreSQL and retrieve typed Python objects — without configuring API or database connectivity in every script.

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
  - [Binary — scheduled sync on a server](#binary--scheduled-sync-on-a-server)
  - [Python library — scripting and automation](#python-library--scripting-and-automation)
- [PostgreSQL Setup](#postgresql-setup)
- [Configuration](#configuration)
- [Running Migrations](#running-migrations)
- [Syncing Data](#syncing-data)
- [Using the Library](#using-the-library)
- [Environment Variables](#environment-variables)
- [Supported Resources](#supported-resources)
- [License](#license)

---

## Requirements

- PostgreSQL 13 or later
- A Meraki Dashboard API key ([how to generate one](https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API#Enable_API_Access))
- Python 3.11 or later *(library install only — not required for the binary)*

---

## Installation

### Binary — scheduled sync on a server

The binary is a self-contained executable that requires no Python installation. It is the recommended choice for running scheduled syncs on a server.

```bash
curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sh
```

This installs `merakisync` to `/usr/local/bin` (or `~/.local/bin` if you do not have write access to `/usr/local/bin`). On Linux servers without write access to `/usr/local/bin`, the script will prompt for `sudo`.

To pin a specific version:

```bash
curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sh -s -- --version v1.0.0
```

To install to a custom directory:

```bash
curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sh -s -- --install-dir /opt/bin
```

The binary provides the full CLI: `merakisync init`, `merakisync migrate`, and `merakisync sync`. It does **not** expose importable Python objects — use the library install below if you need those.

### Python library — scripting and automation

Install via pip to import merakisync objects directly in your own Python scripts:

```bash
pip install merakisync
```

The pip install also provides the `merakisync` CLI command alongside the importable API.

To install from source:

```bash
git clone https://github.com/nathanea05/merakisync
cd merakisync
pip install -e .
```

---

## PostgreSQL Setup

merakisync stores all data in a dedicated schema named `meraki`. The setup requires two separate database connections, so the steps below are split accordingly. Run all commands as a PostgreSQL superuser.

> **Homebrew on macOS:** A fresh Homebrew install does not create a database matching your system username. Always specify a database explicitly when connecting: `psql -d postgres`

### Part 1 — connect to `postgres` and run as superuser

```sql
-- 1. Create the database (skip if using an existing one)
CREATE DATABASE merakisync;

-- 2. Create a dedicated user
CREATE USER merakisync WITH PASSWORD 'your_password_here';
```

### Part 2 — connect to `merakisync` and run as superuser

Disconnect from `postgres` and reconnect to the `merakisync` database before running these statements. In psql, type `\c merakisync`. In a GUI client such as VS Code SQLTools or DBeaver, close the current connection and open a new one targeting the `merakisync` database.

```sql
-- 3. Create the schema and grant ownership
CREATE SCHEMA IF NOT EXISTS meraki AUTHORIZATION merakisync;

-- 4. Grant privileges on the schema
GRANT USAGE, CREATE ON SCHEMA meraki TO merakisync;

-- 5. Grant privileges on future tables and sequences created by migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA meraki
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO merakisync;

ALTER DEFAULT PRIVILEGES IN SCHEMA meraki
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO merakisync;

-- 6. Set the default search path for this user
ALTER ROLE merakisync IN DATABASE merakisync
    SET search_path = meraki, public;
```

> **Remote databases:** If PostgreSQL is not on localhost, update `pg_hba.conf` to allow connections from the host running merakisync and reload the service (`pg_ctlcluster reload` or `systemctl reload postgresql`).

---

## Configuration

Run the interactive setup wizard:

```bash
merakisync init
```

The wizard will:

1. Prompt for your Meraki API key and validate it against the Dashboard.
2. Prompt for PostgreSQL connection details and test the connection.
3. Offer to apply database migrations immediately.
4. Save the configuration to `~/.config/merakisync/config.toml` (mode `600`).

> **Running as root:** Configuration is saved to `/etc/merakisync/config.toml` instead, which is appropriate for system-wide deployments or scheduled jobs running under a service account.

The configuration file looks like this:

```toml
[meraki]
api_key = "your_meraki_api_key"

[database]
host = "localhost"
port = 5432
name = "merakisync"
user = "merakisync"
password = "your_password_here"
```

---

## Running Migrations

Apply the database schema (creates all tables in the `meraki` schema):

```bash
merakisync migrate
```

This runs Alembic migrations up to the latest revision. It is safe to run multiple times — Alembic only applies revisions that have not already been applied.

---

## Syncing Data

### Sync everything

```bash
merakisync sync
```

### Sync specific resource types

```bash
merakisync sync --organizations        # or -o
merakisync sync --networks             # or -n
merakisync sync --devices              # or -d
merakisync sync --switchports
merakisync sync --uplinks
merakisync sync --uplink-usage
merakisync sync --dhcp-server-policy
merakisync sync --alerts
merakisync sync --l3-firewall-rules
merakisync sync --vlans
merakisync sync --ssids
```

Flags can be combined. For example, to sync only networks and devices:

```bash
merakisync sync -n -d
```

### Logging

By default, merakisync logs at INFO level to stdout, which works well with cron and systemd.

```bash
merakisync sync --verbose    # DEBUG level
merakisync sync --quiet      # WARNING level and above only
```

Output is plain text with no colour codes, making it safe to redirect or capture in log files.

### Scheduling recommendations

**Run once daily at midnight UTC.** This keeps data fresh and ensures `UplinkUsage` monthly totals remain accurate.

> **Important:** `UplinkUsage` uses an incremental sync strategy — each run queries only the delta since the last sync and accumulates the bytes onto the stored monthly total. The Meraki API enforces a 14-day maximum query window. If more than 14 days pass between syncs, the data for that gap is unrecoverable and a warning is logged. Run at least once every 14 days to guarantee accurate monthly usage totals.

### Scheduling with cron

```cron
# Sync all data daily at midnight UTC
0 0 * * * /usr/local/bin/merakisync sync >> /var/log/merakisync.log 2>&1
```

### Scheduling with systemd

Create `/etc/systemd/system/merakisync.service`:

```ini
[Unit]
Description=merakisync — sync Meraki data to PostgreSQL
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/merakisync sync
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/merakisync.timer`:

```ini
[Unit]
Description=Run merakisync daily at midnight UTC

[Timer]
OnCalendar=*-*-* 00:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now merakisync.timer
```

---

## Using the Library

> **Requires the Python library install** (`pip install merakisync`). The binary does not expose importable objects.

Once data has been synced, you can retrieve typed Python objects in any script without configuring API or database credentials again.

```python
from merakisync import Organization, Network, Device, Uplink, Switchport

# Retrieve from the database (default)
orgs = Organization.get(source="database")

networks = Network.get(org_id="123456", source="database")

# Filter by product type
switch_networks = Network.get(
    org_id="123456",
    source="database",
    product_types_include=["switch"],
)

# Retrieve directly from the Meraki Dashboard API
devices = Device.get(org_id="123456", source="meraki")

# Retrieve switchports for a specific device
ports = Switchport.get(serial="Q2AB-CDEF-1234", source="database")

# Access typed attributes
for network in networks:
    print(network.name, network.product_types)

for device in devices:
    print(device.serial, device.model, device.status)
```

### Historical data (SCD2)

Most resources use SCD2 versioning. You can query the state of the network at any point in time:

```python
from datetime import datetime, timezone
from merakisync import Device

# Devices as they were on March 1st
snapshot = Device.get(
    org_id="123456",
    source="database",
    ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
)

# All historical versions, not just current
all_versions = Device.get(org_id="123456", source="database", ts="all")
```

### Getting a pre-configured API client or database session

```python
from merakisync import get_dashboard, get_engine, get_session

# Pre-configured Meraki DashboardAPI instance
dashboard = get_dashboard()
raw = dashboard.organizations.getOrganizations()

# Pre-configured SQLAlchemy engine
engine = get_engine()

# Managed database session (commits on exit, rolls back on exception)
with get_session() as session:
    result = session.execute(text("SELECT count(*) FROM meraki.device"))
```

---

## Environment Variables

All configuration values can be supplied or overridden with environment variables. This is useful for containers and CI pipelines where writing a config file is not practical.

| Variable | Description |
|---|---|
| `MERAKI_API_KEY` | Meraki Dashboard API key |
| `MERAKISYNC_DB_HOST` | PostgreSQL host |
| `MERAKISYNC_DB_PORT` | PostgreSQL port (default: `5432`) |
| `MERAKISYNC_DB_NAME` | Database name |
| `MERAKISYNC_DB_USER` | Database user |
| `MERAKISYNC_DB_PASSWORD` | Database password |
| `MERAKISYNC_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |

Environment variables take precedence over values in the config file.

---

## Supported Resources

| Resource | Table | Source | Notes |
|---|---|---|---|
| Organization | `meraki.organization` | Org-level | |
| Network | `meraki.network` | Per-org | |
| Device | `meraki.device` | Per-org | All product types |
| Switchport | `meraki.switchport` | Per-org | MS switches only |
| Uplink | `meraki.uplink` | Per-org | MX/Z devices |
| UplinkUsage | `meraki.uplink_usage` | Per-org | Monthly bandwidth totals; sync at least every 14 days |
| DhcpServerPolicy | `meraki.dhcp_server_policy` | Per-network | Switch networks only |
| Alert | `meraki.alert` | Per-org | Assurance alerts |
| L3FirewallRule | `meraki.l3_firewall_rule` | Per-network | MX appliance networks |
| Vlan | `meraki.vlan` | Per-network | MX appliance networks |
| Ssid | `meraki.ssid` | Per-network | Wireless networks only |

All resources except `UplinkUsage` use SCD2 versioning — historical state is preserved when data changes. `UplinkUsage` stores cumulative monthly byte totals and updates in place.

---

## License

`merakisync` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
