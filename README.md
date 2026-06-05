# merakisync

Sync Meraki Dashboard data into PostgreSQL and retrieve typed Python objects — without configuring API or database connectivity in every script.

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
  - [Binary — scheduled sync on a server](#binary--scheduled-sync-on-a-server)
    - [Updating the binary](#updating-the-binary)
    - [Uninstalling the binary](#uninstalling-the-binary)
  - [Python library — scripting and automation](#python-library--scripting-and-automation)
- [PostgreSQL Setup](#postgresql-setup)
- [Configuration](#configuration)
- [Running Migrations](#running-migrations)
- [Syncing Data](#syncing-data)
  - [Setting up a service account](#setting-up-a-service-account)
  - [Scheduling with systemd (recommended)](#scheduling-with-systemd-recommended)
  - [Scheduling with cron](#scheduling-with-cron)
- [Using the Library](#using-the-library)
- [Environment Variables](#environment-variables)
- [Supported Resources](#supported-resources)
- [License](#license)

---

## Requirements

- **Ubuntu 22.04 or later** — merakisync is developed and tested on Ubuntu. It may work on other Linux distributions or macOS, but these are not supported.
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

**Updating the binary**

Re-run the same install command. It overwrites the binary in place — no service restart required. After updating, run `merakisync migrate` to apply any new database migrations before the next sync runs.

```bash
curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sh
merakisync migrate
```

**Uninstalling the binary**

Remove the binary and, optionally, the configuration file:

```bash
# Remove the binary (use the path reported during installation)
rm /usr/local/bin/merakisync
# or, if installed to ~/.local/bin:
rm ~/.local/bin/merakisync

# Optional: remove the configuration file
rm -rf ~/.config/merakisync/       # regular user
# or, if installed as root:
rm -rf /etc/merakisync/
```

The PostgreSQL database and schema are not touched by uninstall. Drop them manually if you no longer need the data:

```sql
DROP SCHEMA meraki CASCADE;
```

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

merakisync stores all data in a dedicated schema named `meraki`. Run all commands as a PostgreSQL superuser.

> **Database and user names:** The examples below use `merakisync` for both the database and the user. You can choose different names — just use them consistently in every command below and enter the same values when running `merakisync init`.

> **Remote databases:** If PostgreSQL is not on localhost, update `pg_hba.conf` to allow connections from the host running merakisync and reload the service (`pg_ctlcluster reload` or `systemctl reload postgresql`).

### Step 1 — open a superuser session on the `postgres` database

```bash
psql -d postgres
```

> **Homebrew on macOS:** A fresh Homebrew install does not create a database matching your system username, so you must specify `-d postgres` explicitly.

### Step 2 — create the database and user

```sql
CREATE DATABASE merakisync;
CREATE USER merakisync WITH PASSWORD 'your_password_here';
```

### Step 3 — switch to the new database

The next commands must run inside the `merakisync` database, not `postgres`. Stay in the same psql session and run:

```sql
\c merakisync
```

If you are using a GUI client (VS Code SQLTools, DBeaver, etc.), close the current connection and open a new one targeting the `merakisync` database before continuing.

### Step 4 — create the schema and grant privileges

```sql
CREATE SCHEMA IF NOT EXISTS meraki AUTHORIZATION merakisync;

GRANT USAGE, CREATE ON SCHEMA meraki TO merakisync;

ALTER DEFAULT PRIVILEGES IN SCHEMA meraki
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO merakisync;

ALTER DEFAULT PRIVILEGES IN SCHEMA meraki
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO merakisync;

ALTER ROLE merakisync IN DATABASE merakisync
    SET search_path = meraki, public;
```

---

## Configuration

> **Setting up a scheduled sync?** If you're deploying merakisync as a system service under a dedicated account — the recommended production setup — skip ahead to [Setting up a service account](#setting-up-a-service-account). That section covers binary installation, `init`, and migrations all in one place under the service account. You do not need to run `merakisync init` as your own user first.

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

> **Important:** `UplinkUsage` uses an incremental sync strategy — each run queries only the delta since the last sync and accumulates the bytes onto the stored monthly total. Each query covers at most 14 days (the API's per-query maximum), but gaps up to 30 days are fully recoverable across multiple syncs. If more than 30 days pass between syncs, data beyond the 30-day lookback limit is unrecoverable and a warning is logged.

### Setting up a service account

Run merakisync under a dedicated system account rather than your own user or root. The steps below set up that account, install the binary, and configure merakisync — all on the Ubuntu server that will run the scheduled sync.

#### Step 1 — create the service account

```bash
sudo useradd --system --shell /usr/sbin/nologin --create-home --home-dir /var/lib/merakisync merakisync
```

This creates a system account with no login shell and a home directory at `/var/lib/merakisync`. merakisync will store its config file there.

#### Step 2 — install the binary

```bash
curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sudo sh -s -- --install-dir /usr/local/bin
```

#### Step 3 — run the setup wizard as the service account

```bash
sudo -u merakisync merakisync init
```

The wizard will prompt for your Meraki API key and PostgreSQL connection details, test both connections, and save the config to `/var/lib/merakisync/.config/merakisync/config.toml`.

#### Step 4 — apply database migrations

```bash
sudo -u merakisync merakisync migrate
```

### Scheduling with systemd (recommended)

#### Step 1 — create the service unit

Create `/etc/systemd/system/merakisync.service`:

```ini
[Unit]
Description=merakisync — sync Meraki data to PostgreSQL
After=network.target

[Service]
Type=oneshot
User=merakisync
ExecStart=/usr/local/bin/merakisync sync
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Step 2 — create the timer unit

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

#### Step 3 — enable and start the timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now merakisync.timer
```

#### Step 4 — verify

```bash
systemctl status merakisync.timer
```

You should see `Active: active (waiting)` and the next trigger time listed. To run a sync immediately and check the output:

```bash
sudo systemctl start merakisync.service
journalctl -u merakisync.service -n 50
```

### Scheduling with cron

If you prefer cron over systemd, install the crontab for the service account:

```bash
sudo crontab -u merakisync -e
```

Add the following line:

```cron
0 0 * * * /usr/local/bin/merakisync sync >> /var/log/merakisync.log 2>&1
```

Create the log file and give the service account write access:

```bash
sudo touch /var/log/merakisync.log
sudo chown merakisync:merakisync /var/log/merakisync.log
```

---

## Using the Library

> **Requires the Python library install** (`pip install merakisync`). The binary does not expose importable objects.

merakisync works with whichever connections you have available. You do not need both a Meraki API key and a database — configure only what you need:

| What you have | What you can do |
|---|---|
| **Meraki API key only** | Fetch typed objects directly from the Dashboard (`source="meraki"`). No database required. Useful for one-off scripts and tools that don't need persistence. |
| **Database only** | Query typed objects synced by another process or another team (`source="database"`). No API key required. Useful when you have read access to a shared merakisync database but no Dashboard credentials. |
| **Both** | Full functionality — run syncs to populate the database and query historical data from it. |

Configure your available credentials via the [config file or environment variables](#environment-variables) and merakisync will use what is present.

```python
from merakisync import Organization, Network, Device, Uplink, Switchport

# Retrieve from the database (default) — no API key needed
orgs = Organization.get(source="database")

networks = Network.get(org_id="123456", source="database")

# Filter by product type
switch_networks = Network.get(
    org_id="123456",
    source="database",
    product_types_include=["switch"],
)

# Retrieve directly from the Meraki Dashboard API — no database needed
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
| UplinkUsage | `meraki.uplink_usage` | Per-org | Monthly bandwidth totals; data unrecoverable after 30-day gap |
| DhcpServerPolicy | `meraki.dhcp_server_policy` | Per-network | Switch networks only |
| Alert | `meraki.alert` | Per-org | Assurance alerts |
| L3FirewallRule | `meraki.l3_firewall_rule` | Per-network | MX appliance networks |
| Vlan | `meraki.vlan` | Per-network | MX appliance networks |
| Ssid | `meraki.ssid` | Per-network | Wireless networks only |

All resources except `UplinkUsage` use SCD2 versioning — historical state is preserved when data changes. `UplinkUsage` stores cumulative monthly byte totals and updates in place.

---

## License

`merakisync` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
