# Troubleshooting

This document covers the most common problems encountered when running merakisync and explains how to diagnose and fix them.

---

## General diagnostic steps

Run with `--verbose` first. Most problems produce a clear error message at DEBUG level that is suppressed at the default INFO level:

```bash
merakisync sync --verbose 2>&1 | head -50
```

Check the configuration is loading correctly:

```bash
python3 -c "from merakisync.config import get_config; c = get_config(); print(c.db.host, c.db.name)"
```

Check the database is reachable:

```bash
python3 -c "from merakisync.database import validate_connection; validate_connection(); print('OK')"
```

Check the API key is valid:

```bash
python3 -c "from merakisync.config import get_config; from merakisync.dashboard import validate_api_key; validate_api_key(get_config().meraki_api_key); print('OK')"
```

---

## Configuration

### `MissingConfigError: No configuration found`

**Cause:** The config file does not exist and no environment variables were set.

**Fix:** Run `merakisync init` to create the config file, or set the `MERAKI_API_KEY` and `MERAKISYNC_DB_*` environment variables.

**Where the config file should be:**
- Regular user: `~/.config/merakisync/config.toml`
- Root / system service: `/etc/merakisync/config.toml`
- Custom path: set `XDG_CONFIG_HOME` before running.

```bash
# Confirm the path merakisync is looking at
python3 -c "from merakisync.config import get_save_path; print(get_save_path())"
```

### `MissingConfigError: Meraki API key is missing`

**Cause:** The config file exists but `[meraki] api_key` is blank, or `MERAKI_API_KEY` is set to an empty string.

**Fix:** Re-run `merakisync init` or edit the config file directly and set `api_key`.

### Config file changes are not being picked up

**Cause:** `get_engine()` and `get_dashboard()` are cached with `@lru_cache`. If the config was changed after the process started, the old DSN and API key remain cached.

**Fix:** Restart the process. If you are running merakisync as a long-lived service (not as cron jobs), send `SIGHUP` or restart the service after changing the config.

### `port` is read as a string instead of an integer

**Cause:** An older config file written by a previous version may have quoted the port value: `port = "5432"` instead of `port = 5432`.

**Fix:** Edit `~/.config/merakisync/config.toml` and remove the quotes from the port value.

---

## Database connectivity

### `DatabaseConnectionError: Database connection failed`

**Cause:** PostgreSQL is not reachable, the credentials are wrong, or the database does not exist.

**Diagnose:**

```bash
# Try connecting directly with psql
psql "postgresql://merakisync:yourpassword@yourhost:5432/merakisync"
```

Common sub-causes:

| Symptom | Likely cause |
|---|---|
| `Connection refused` | PostgreSQL is not running or is not listening on that port |
| `FATAL: password authentication failed` | Wrong username or password |
| `FATAL: database "..." does not exist` | Database was not created |
| `could not connect to server: No route to host` | Firewall or wrong host |
| `FATAL: no pg_hba.conf entry for host` | Remote connections not allowed in `pg_hba.conf` |

**Fix for remote connections:** Add a line to `pg_hba.conf` on the PostgreSQL server:

```
host    merakisync    merakisync    <client_ip>/32    scram-sha-256
```

Then reload: `systemctl reload postgresql` or `pg_ctlcluster <version> main reload`.

### `sqlalchemy.exc.ProgrammingError: schema "meraki" does not exist`

**Cause:** The `meraki` schema was not created, or the database user does not have access to it.

**Fix:** Run the PostgreSQL setup SQL from the README, then run `merakisync migrate`.

### `sqlalchemy.exc.ProgrammingError: relation "meraki.organization" does not exist`

**Cause:** Migrations have not been applied.

**Fix:**

```bash
merakisync migrate
```

If `merakisync migrate` fails, check `alembic current` to see what state the database is in, and check the migration files for syntax errors.

---

## Meraki API

### `MerakiConnectionError: Meraki API Key Validation failed`

**Cause:** The API key is invalid, expired, or has been revoked.

**Fix:** Generate a new API key in the Meraki Dashboard under **My Profile → API access** and re-run `merakisync init`.

### `APIError: 404 Not Found`

**Cause:** The endpoint does not exist for this network or organization. Common examples:
- Calling `getNetworkSwitchDhcpServerPolicy` on a network that has no switch devices.
- Calling `getNetworkApplianceFirewallL3FirewallRules` on a network that is not an appliance network.

**Fix:** `cmd_sync.py` already guards these with `"switch" in product_types` and `"appliance" in product_types` checks. If you are calling API methods directly, add a product type guard before making the call.

### `APIError: 429 Too Many Requests`

**Cause:** The Meraki API rate limit was hit.

**Fix:** The Meraki SDK is configured with `wait_on_rate_limit=True` and `maximum_retries=10` (see `dashboard.py`). The SDK will back off and retry automatically. If this happens frequently, reduce sync frequency or contact Meraki support to discuss rate limit increases.

### `APIError: 400 Bad Request`

**Cause:** An invalid parameter was passed to the API.

**Diagnose:** Run with `--verbose` and look for the full error message, which usually includes the invalid parameter name.

### Meraki API returns different fields than expected

**Cause:** Meraki occasionally changes API responses across firmware versions or feature rollouts. A field that is always present for one network may be absent for another.

**Fix:** Make the corresponding model field optional (`field: str | None = None`). The `from_dashboard()` method silently ignores keys that do not map to a model field, and missing keys result in the default `None` value for optional fields.

---

## Sync behaviour

### Data is not being updated in the database

**Cause A:** The SCD2 change detection considers the data unchanged because the comparison is using stale or serialised values.

**Diagnose:** Query the database for the current row and compare it to what the API is returning:

```python
from merakisync import Network, get_dashboard

# Get from API
api_networks = Network.get(org_id="YOUR_ORG_ID", source="meraki")

# Get from DB (current rows only)
db_networks = Network.get(org_id="YOUR_ORG_ID", source="database")

api = {n.id: n for n in api_networks}
db  = {n.id: n for n in db_networks}

for nid in api:
    if nid in db:
        a = api[nid]._data_fields()
        d = db[nid]._data_fields()
        if a != d:
            print(f"{nid} differs")
            for k in a:
                if a[k] != d[k]:
                    print(f"  {k}: api={a[k]!r}  db={d[k]!r}")
```

**Cause B:** `upsert()` UPDATE was not committed. This was a bug in the original codebase that has been fixed — if you see it, check that you are running the current version.

### SCD2 is creating too many new rows (lots of `expired+inserted` operations)

**Cause:** A field that changes frequently (e.g., a timestamp, a counter, or an object that Meraki returns in a non-deterministic order) is being included in the data comparison.

**Diagnose:** Use the script above to identify which field is driving the difference.

**Fix options:**
1. If the field is not meaningful for change detection, exclude it from the model (do not add it as a dataclass field) or move it to a separate model.
2. If the field is a JSON object or list whose key order varies, the `_data_equal()` function in `models/base.py` handles JSON strings vs. Python dicts, but does not sort list elements. You may need to normalise the value in `from_dashboard()` before it is stored.

### `upsert_many` is slow for large data sets

**Cause:** Each row in `upsert_many` does at least one `SELECT` (to find the current row) and potentially one or two `UPDATE`/`INSERT` statements. For 10,000 devices this is 10,000–30,000 queries in a single transaction, which can take 30–90 seconds depending on database latency.

**Short-term mitigation:** Ensure the database has the composite indexes created by the initial migration (`ix_device_serial_active`, etc.). Without these indexes, each `SELECT` does a full table scan.

**Long-term:** If sync times become unacceptable, the upsert logic in `models/base.py` can be replaced with a bulk approach: write all incoming rows to a temporary table and use a single SQL `MERGE` or multi-row `INSERT … ON CONFLICT` statement. This is a significant change and should be done as a planned optimisation, not a quick fix.

---

## Migrations

### `alembic.util.exc.CommandError: Can't locate revision identified by '...'`

**Cause:** The `alembic_version` table in the database references a revision ID that no longer exists in the `migrations/versions/` directory.

**Fix:** This usually happens when a migration file was renamed or deleted after being applied. Do not delete or rename applied migration files. To fix it:

```sql
-- Check what revision is recorded
SELECT * FROM alembic_version;

-- If the revision file no longer exists, manually stamp to a known good revision
-- (run this from the CLI, not directly in SQL)
alembic stamp 0001
```

Then re-run `alembic upgrade head`.

### `FAILED: Target database is not up to date`

**Cause:** Multiple processes are trying to run migrations at the same time.

**Fix:** Ensure only one process runs migrations at a time (e.g., only in `merakisync init` or a dedicated deploy step, not on every sync run).

---

## Import errors

### `ImportError: cannot import name 'get_engine' from 'merakisync.db.engine'`

**Cause:** Old code is importing from `merakisync.db.engine`, which was removed. The engine is now in `merakisync.database`.

**Fix:** Update the import:

```python
# Old (removed)
from merakisync.db.engine import get_engine

# New
from merakisync.database import get_engine
```

### `ImportError: circular import`

**Cause:** A model file is importing from `merakisync` (the package root) rather than from the specific submodule.

**Fix:** Change the import to use the specific module path:

```python
# Wrong — causes circular import
from merakisync import get_dashboard, get_engine

# Correct
from merakisync.dashboard import get_dashboard
from merakisync.database import get_engine
```

These imports should also be placed **inside** the `get()` and `sync()` method bodies rather than at the top of the file, as a secondary safeguard against circular imports.

---

## Getting additional diagnostic information

To see every SQL statement merakisync sends to the database, set the SQLAlchemy log level to `INFO`:

```bash
MERAKISYNC_LOG_LEVEL=DEBUG python3 -c "
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
from merakisync import Organization
orgs = Organization.get(source='database')
print(len(orgs))
"
```

To see every Meraki API call, run with the Meraki SDK's output enabled:

```python
from merakisync.dashboard import create_dashboard, DashboardDefaults
from merakisync.config import get_config

conf = get_config()
debug_dashboard = create_dashboard(
    conf.meraki_api_key,
    defaults=DashboardDefaults(suppress_logging=False, print_console=True, output_log=False)
)
```
