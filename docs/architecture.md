# Architecture Overview

This document explains how merakisync is structured and why, so that a new developer can navigate the codebase, understand its design decisions, and make changes confidently.

---

## Purpose

merakisync does two things:

1. **Sync** — Pull data from the Meraki Dashboard API and write it to PostgreSQL.
2. **Retrieve** — Let other scripts import typed Python objects from the database (or directly from the API) without setting up credentials themselves.

It deliberately does nothing else. Keep it that way.

---

## Directory structure

```
src/merakisync/
│
├── __init__.py          Public API surface. Re-exports the things callers need.
├── __about__.py         Package version string.
├── exceptions.py        All custom exceptions. Import from here, not from individual modules.
├── config.py            Configuration dataclasses, TOML read/write, env var overlay.
├── dashboard.py         Meraki DashboardAPI factory. Cached singleton per API key.
├── database.py          SQLAlchemy engine factory. Cached singleton per DSN.
├── logging.py           Logging setup for cron/systemd environments.
│
├── cli/
│   ├── cli.py           Entry point. Builds the argparse tree and dispatches.
│   ├── cmd_init.py      `merakisync init` — interactive setup wizard.
│   ├── cmd_migrate.py   `merakisync migrate` — runs Alembic upgrade head.
│   └── cmd_sync.py      `merakisync sync` — orchestration. Calls model .sync() methods.
│
├── migrations/
│   ├── env.py           Alembic env. Injects DSN from merakisync config.
│   ├── script.py.mako   Template for new migration files.
│   └── versions/        One file per migration revision.
│
├── models/
│   ├── base.py          MerakiObj base class. Owns upsert, SCD2, from_dashboard, from_row.
│   ├── organization.py
│   ├── network.py
│   ├── device.py
│   ├── switchport.py
│   ├── uplink.py
│   ├── uplink_usage.py
│   ├── dhcp_server_policy.py
│   ├── alert.py
│   └── l3_firewall_rule.py
│
└── utils/
    ├── casing.py        camel_to_snake conversion.
    ├── confirm.py       y/n prompt helper.
    ├── prompt.py        General input prompt helper.
    ├── filter_array.py  Include/exclude set filtering.
    └── action_batch.py  Meraki action batch builder/sender.
```

---

## Data flow

### Sync path (Meraki → PostgreSQL)

```
CLI (cmd_sync.py)
  └─ Model.sync(...)
       ├─ Model.get(source="meraki")
       │    └─ dashboard.organizations.getSomething(...)   # Meraki SDK call
       │         └─ Model.from_dashboard(raw_dict)         # camelCase → snake_case
       └─ Model.upsert_many(rows)                          # Single connection, one transaction
            └─ MerakiObj._upsert_with_conn(conn)
                 ├─ SCD2: query current row → compare → expire/insert/touch
                 └─ Simple UPSERT: INSERT … ON CONFLICT DO UPDATE
```

### Retrieval path (PostgreSQL → caller)

```
Caller: Network.get(org_id="...", source="database")
  └─ database.get_engine()                     # Cached SQLAlchemy engine
       └─ engine.connect()
            └─ SELECT * FROM meraki.network WHERE ...
                 └─ Model.from_row(row)        # DB row → typed dataclass
```

### Retrieval path (Meraki API → caller)

```
Caller: Device.get(org_id="...", source="meraki")
  └─ dashboard.get_dashboard()                 # Cached DashboardAPI instance
       └─ dashboard.organizations.getOrganizationDevices(...)
            └─ Model.from_dashboard(raw_dict)  # camelCase → typed dataclass
```

---

## Key design patterns

### MerakiObj base class

Every model inherits from `MerakiObj` (defined in `models/base.py`). The base class provides:

- `from_dashboard(data)` — converts a raw Meraki API response dict into a model instance. Applies `__mapping_override__` first, then falls back to `camel_to_snake` for any unmapped key.
- `from_row(row)` — converts a SQLAlchemy row or dict (already snake_case) into a model instance.
- `to_dict()` — returns all dataclass fields as a plain dict.
- `_data_fields()` — returns only business-data fields (excludes PK columns and SCD2 timestamp fields). Used for change detection.
- `upsert(engine)` — persists a single row with SCD2 or simple UPSERT logic.
- `upsert_many(rows, engine)` — persists a sequence of rows in a single connection and transaction. Always use this for syncing collections.

Each model controls the base class behaviour via class variables:

| Variable | Type | Purpose |
|---|---|---|
| `__table_name__` | `str` | Database table name. Defaults to snake_case of class name. |
| `__pk__` | `tuple[str, ...]` | Primary key column names (snake_case). |
| `__schema__` | `str` | Database schema. Defaults to `"meraki"`. |
| `__mapping_override__` | `dict[str, str]` | Maps `model_field → dashboard_key` for fields that don't follow camelCase. |
| `__versioned__` | `bool` | `True` (default) = SCD2 logic. `False` = simple INSERT … ON CONFLICT DO UPDATE. |

### SCD2 versioning

SCD2 (Slowly Changing Dimension Type 2) preserves history by never overwriting rows. Instead:

- **Current rows** have `active_to IS NULL`.
- When data changes, the current row is expired (`active_to = now()`) and a new row is inserted (`active_from = now(), active_to = NULL`).
- When data has not changed, only `last_seen` is updated.

Change detection compares only business-data fields — PK columns and versioning fields (`active_from`, `active_to`, `last_seen`) are excluded from the comparison. JSON blobs stored as text in the DB are decoded before comparison.

`UplinkUsage` opts out of SCD2 with `__versioned__ = False` because it is a rolling metric (cumulative monthly bytes), not a configuration state.

### Avoiding circular imports

The package `__init__.py` re-exports everything callers need, but the models must not import from `merakisync` (the package root) because the package root imports the models — that creates a circular dependency.

**Rule:** Model files import directly from the submodule, never from the root package.

```python
# Correct — inside a model file
from merakisync.dashboard import get_dashboard
from merakisync.database import get_engine

# Wrong — creates a circular import
from merakisync import get_dashboard, get_engine
```

Additionally, dashboard and engine imports inside model methods are deferred (placed inside the function body) so they only resolve at call time, not at module load time. This further prevents import-order issues.

### Singleton engine and dashboard

`get_engine()` and `get_dashboard()` use `@lru_cache`. The first call creates the object; subsequent calls return the same instance. This means the database connection pool and the Meraki SDK session are shared across the entire process rather than being recreated for every model method call.

The cache key for `get_engine()` is the DSN string. The cache key for `get_dashboard()` is the API key string. If you need to reset them (e.g., in tests), call `get_engine.cache_clear()` or `reset_dashboard_cache()`.

### Configuration and env vars

Configuration is loaded by `config.get_config()`. It reads `~/.config/merakisync/config.toml` first, then overlays any `MERAKI_API_KEY` or `MERAKISYNC_DB_*` environment variables on top. Env vars always win. This means containers and CI can inject secrets without touching the config file.

---

## What belongs where

| Concern | Where it lives |
|---|---|
| Meraki API field mapping | `__mapping_override__` on the model class |
| camelCase → snake_case conversion | `utils/casing.py`, called by `MerakiObj.from_dashboard()` |
| Database schema | `models/base.py` (`__schema__`), migration file |
| Upsert / SCD2 logic | `models/base.py` only — no model re-implements this |
| Sync orchestration (what order, which networks get which resources) | `cli/cmd_sync.py` |
| Per-resource sync logic | `Model.sync()` on the model class |
| All custom exceptions | `exceptions.py` |
| Logging configuration | `logging.py`, called once at CLI startup |
| Database migrations | `migrations/versions/` |

---

## Things to avoid

- **Do not import from `merakisync` inside model files.** Import from `merakisync.dashboard`, `merakisync.database`, etc. directly.
- **Do not call `upsert()` in a loop.** Use `upsert_many()` whenever syncing more than one object.
- **Do not put business logic in the CLI modules.** `cli/cmd_sync.py` orchestrates; models do the work.
- **Do not reimplement `from_dashboard` or `from_row` in a model unless you have a specific reason** (e.g., `Alert` needs to flatten a nested object). The base class handles the general case.
- **Do not add a new exception class anywhere except `exceptions.py`.**
- **Do not hardcode DSNs, API keys, or passwords anywhere in the codebase.**
