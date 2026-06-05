# CLAUDE.md — merakisync

---

## Purpose

You are assisting in building **merakisync**: a tool that syncs Meraki Dashboard data into PostgreSQL and exposes it as typed Python objects.

merakisync serves two audiences:

1. **Sysadmins** — install the self-contained binary via `curl` and run `merakisync sync` on a schedule. No Python required.
2. **Automation engineers** — install via `pip install merakisync` and import typed objects (`Organization`, `Network`, `Switchport`, etc.) directly in their scripts without re-implementing API or database connectivity.

This library is the data foundation for a future tool called **merakiops**, which will use these objects for automation, reporting, and remediation workflows.

Your job is to build a system that is **reliable**, **scalable**, **modular**, **maintainable**, and **explicit** — in that order of priority.

---

## Developer context

The developer is a network engineer managing hundreds of Meraki networks who writes production automation in Python. They:

- Value reliability and debuggability over cleverness.
- Prefer clear, structured code over abstraction for abstraction's sake.
- Will maintain and extend this codebase long-term.
- Want code they can hand to a colleague without explanation.

---

## Guiding philosophy

### 1. POSIX/UNIX philosophy — do one thing well

This project handles exactly two concerns:

1. Syncing Meraki Dashboard data → PostgreSQL.
2. Retrieving that data as typed Python objects (from the DB or directly from the API).

Do not add alerting, remediation, scheduling, dashboarding, or any other feature. If it does not directly serve sync or retrieval, it does not belong here.

### 2. Boring over clever

- Simple > clever abstractions.
- Explicit > implicit.
- Readable > DRY (within reason).
- Avoid metaprogramming. Do not use `__init_subclass__`, dynamic class factories, or class decorators unless there is no simpler alternative.

### 3. Production mindset

Assume:
- Thousands of Meraki networks.
- Tens of thousands of devices.
- Repeated scheduled runs (cron/systemd).
- Failures must be visible, logged, and debuggable without a debugger attached.

### 4. Idempotency

Every sync operation must be safe to run multiple times with the same result. Never create duplicate active records. Never silently skip failures.

---

## Distribution

merakisync ships in two forms. Both use the same source code and configuration.

**Binary (PyInstaller)** — a self-contained executable for sysadmins running scheduled syncs. Installed via `install.sh`. No Python required on the target machine. Provides the CLI only (`init`, `migrate`, `sync`). Does not expose importable Python objects.

**Python library (pip)** — installed via `pip install merakisync`. Provides both the CLI and importable objects (`from merakisync import Organization, Network, ...`) for use in automation scripts.

### Release artifact naming

PyInstaller must be run on each target platform. Release binaries are named:

| Platform | Binary name |
|---|---|
| macOS Apple Silicon | `merakisync-darwin-arm64` |
| macOS Intel | `merakisync-darwin-x86_64` |
| Linux x86_64 | `merakisync-linux-x86_64` |
| Linux ARM64 | `merakisync-linux-arm64` |

Each release also includes a `checksums.txt` with SHA-256 hashes in `<hash>  <name>` format.

### PyInstaller spec

`merakisync.spec` at the project root controls the frozen build. When adding a new dependency to `pyproject.toml`, check whether its modules are loaded dynamically (via string, entry point, or `importlib`) — if so, add them to `hiddenimports` in the spec. SQLAlchemy dialects, Alembic internals, and Mako are examples of modules that must be listed explicitly.

The venv used to build **must** have all project dependencies installed (`pip install -e .`) before running `pyinstaller merakisync.spec`.

---

## Project structure

```
install.sh               Curl-installable binary installer for macOS and Linux.
merakisync.spec          PyInstaller spec for the self-contained binary build.
src/merakisync/
├── __init__.py          Thin public re-exports. No business logic.
├── __about__.py         Version string only.
├── exceptions.py        All custom exceptions. The only place they are defined.
├── config.py            Configuration dataclasses + TOML read/write + env overlay.
├── dashboard.py         Meraki DashboardAPI factory (lru_cache singleton).
├── database.py          SQLAlchemy engine + session factory (lru_cache singleton).
├── logging.py           Logging setup for cron/systemd environments.
├── cli/
│   ├── cli.py           Entry point. Arg parsing and dispatch only. No logic.
│   ├── cmd_init.py      `merakisync init` wizard.
│   ├── cmd_migrate.py   `merakisync migrate` — Alembic upgrade head.
│   └── cmd_sync.py      `merakisync sync` — orchestration only. Calls Model.sync().
├── migrations/
│   ├── env.py           Alembic env. Reads DSN from merakisync config.
│   ├── script.py.mako   Migration file template.
│   └── versions/        One file per migration: 0001_..., 0002_..., etc.
├── models/
│   ├── base.py          MerakiObj. All shared logic lives here.
│   ├── organization.py
│   ├── network.py
│   ├── device.py
│   ├── switchport.py
│   ├── uplink.py
│   ├── uplink_usage.py
│   ├── dhcp_server_policy.py
│   ├── alert.py
│   ├── l3_firewall_rule.py
│   ├── vlan.py
│   └── ssid.py
└── utils/
    ├── casing.py        camel_to_snake / snake_to_camel.
    ├── confirm.py       y/n prompt.
    ├── prompt.py        General input prompt.
    ├── filter_array.py  Include/exclude set filtering.
    └── action_batch.py  Meraki action batch helpers.
```

### Strict boundary rules

| Concern | Lives in | Must not appear in |
|---|---|---|
| Meraki API calls | model `get()` / `sync()` | CLI, `database.py`, `config.py` |
| Database queries | model `get()`, `MerakiObj.upsert*` | CLI, `dashboard.py`, `config.py` |
| Sync orchestration (order, which networks get which resources) | `cli/cmd_sync.py` | models |
| Per-resource sync logic | `Model.sync()` | CLI |
| All custom exceptions | `exceptions.py` | everywhere else |
| Credentials / secrets | config file or env vars | source code |

---

## Data flow

All data follows these two paths and no others.

**Sync (Meraki → DB):**
```
Meraki API → Model.from_dashboard(raw_dict) → model instance → Model.upsert_many(rows)
```

**Retrieval (DB → caller):**
```
SELECT * FROM meraki.table → Model.from_row(row) → model instance
```

**Retrieval (API → caller):**
```
Meraki API → Model.from_dashboard(raw_dict) → model instance
```

No shortcuts. No passing raw dicts to callers.

---

## The base class — MerakiObj

Every model inherits from `MerakiObj` in `models/base.py`.

### Class variables every model must set

```python
__table_name__: ClassVar[str]              # snake_case table name, no schema
__pk__: ClassVar[tuple[str, ...]]          # tuple of snake_case PK column names
__schema__: ClassVar[str] = "meraki"       # override only if using a different schema
__mapping_override__: ClassVar[dict[str, str]]  # {model_field: dashboard_key}
__versioned__: ClassVar[bool] = True       # False = simple UPSERT (see below)
```

### `__mapping_override__` format

The dict maps **model field name → Meraki API key name**. Only add entries for fields that cannot be handled by automatic `camel_to_snake` conversion: Python reserved words (`type`), injected fields, or irregular capitalisation.

```python
__mapping_override__ = {
    "alert_type": "type",       # "type" is a Python builtin
    "ip_assigned_by": "ipAssignedBy",  # camel_to_snake gets this right — no entry needed
}
```

### Methods provided by the base class

- `from_dashboard(data: dict)` → model instance. Applies `__mapping_override__`, then `camel_to_snake`.
- `from_row(row)` → model instance. Accepts dict, SQLAlchemy Row, or RowMapping.
- `to_dict()` → all fields as a plain dict.
- `_data_fields()` → business-data fields only (excludes PK and versioning fields). Used for SCD2 change detection.
- `upsert(engine=None)` → persists one row. Returns `"inserted"`, `"updated"`, or `"expired+inserted"`.
- `upsert_many(rows, engine=None)` → persists a sequence in a **single connection and transaction**. Always use this when syncing a collection. Never call `upsert()` in a loop.

---

## SCD2 versioning

Every SCD2 model table has three timestamp columns:

| Column | Meaning |
|---|---|
| `active_from` | When this version of the row became active |
| `active_to` | When this version was superseded (`NULL` = currently active) |
| `last_seen` | When the data was last confirmed unchanged |

**Rules:**
- There must be exactly one active row per unique object (`active_to IS NULL`).
- If data changes: expire the old row (`active_to = now()`), insert a new row (`active_from = now()`).
- If data is unchanged: update `last_seen` only.
- Change detection compares business-data fields only — PK columns and the three timestamp columns are excluded.
- **Never overwrite an active row. Never delete rows.**

### The SCD2 exception — UplinkUsage

`UplinkUsage` sets `__versioned__ = False`. It tracks cumulative monthly bandwidth bytes — a rolling metric, not a configuration state. Its upsert uses `INSERT … ON CONFLICT DO UPDATE` to accumulate byte counts in place. It has a `last_seen` column but no `active_from` or `active_to`. This is the only current model that behaves this way.

**Incremental sync strategy:** `sync()` reads `last_seen` from existing DB records as `t0`, queries the Meraki API only for the delta window since the last sync (`t0 → now`), and accumulates those bytes onto the stored totals before upserting. `last_seen` is set to `t1` (the end of the queried window), not to wall-clock time, so the next sync continues from exactly where this one ended. Each sync covers at most a 14-day window (the API's per-query maximum). Gaps up to 30 days are fully recoverable across multiple syncs. If more than 30 days pass between syncs, data beyond the 30-day lookback limit is unrecoverable and a `WARNING` is logged.

**Overridable `last_seen` in `_simple_upsert`:** Unlike SCD2 models (which always write `last_seen = now()`), the simple upsert path uses the `last_seen` value from the object itself if it is not `None`, and falls back to `now()` only when it is `None`. This allows `sync()` to write `last_seen = t1` precisely.

---

## Model structure

Each model file follows this pattern:

```python
@dataclass()
class Vlan(MerakiObj):
    __table_name__: ClassVar[str] = "vlan"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id", "vlan_id")
    __mapping_override__: ClassVar[dict[str, str]] = { ... }

    # 1. PK fields (required, no default)
    # 2. Required business fields
    # 3. Optional business fields (= None)
    # 4. Versioning fields last (always Optional, = None)
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None

    @property
    def resource_path(self) -> str:
        return f"/networks/{self.network_id}/appliance/vlans/{self.vlan_id}"

    @classmethod
    def get(cls, ..., source: Literal["database", "meraki"] = "database", ...) -> list[I]:
        ...

    @classmethod
    def sync(cls, ...) -> list[I]:
        rows = cls.get(..., source="meraki")
        counts = cls.upsert_many(rows)
        logger.info(...)
        return rows
```

### `resource_path` rules

- Every model must implement `resource_path` as a `@property` returning a `str`.
- Use the single-resource GET path from the Meraki API docs (e.g., `/devices/{serial}/switch/ports/{portId}`).
- If no per-resource endpoint exists (the resource is only returned as part of a collection), return the collection endpoint and document the limitation in the docstring. See `L3FirewallRule` and `UplinkUsage`.
- If the resource requires a parent ID not stored on the model, return the closest navigable path from available fields and document the constraint. See `Uplink`.

### `get()` rules

- Default `source` to `"database"` — reading from the DB is the common case.
- Valid source values: `"database"` and `"meraki"` (not `"db"` or `"dashboard"`).
- Always raise `ValueError` if `ts` is used with `source="meraki"`.
- Import `get_dashboard` and `get_engine` **inside** the if-branches, not at the top of the file. This prevents circular imports.
- Return `list[I]`, not `list[I] | None`. Return an empty list when nothing is found.
- Always filter current rows with `active_to IS NULL` by default (when `ts` is `None`).

### `sync()` rules

- Always call `upsert_many()`, never `upsert()` in a loop.
- Use `logger.debug` for per-resource messages that repeat thousands of times. Use `logger.info` for org-level summaries.
- Return the list of synced objects.

---

## Circular import rule — critical

The package `__init__.py` imports from the models. The models must therefore **never** import from `merakisync` (the package root).

```python
# WRONG — causes a circular import
from merakisync import get_dashboard, get_engine

# CORRECT — import directly from the submodule
from merakisync.dashboard import get_dashboard
from merakisync.database import get_engine
```

Place these imports **inside** the method body (deferred import), not at the top of the model file, as a secondary safeguard.

---

## CLI rules

```
merakisync init                       # Setup wizard
merakisync migrate                    # Alembic upgrade head
merakisync sync                       # All resource types
merakisync sync -o / --organizations
merakisync sync -n / --networks
merakisync sync -d / --devices
merakisync sync --switchports
merakisync sync --uplinks
merakisync sync --uplink-usage
merakisync sync --dhcp-server-policy
merakisync sync --alerts
merakisync sync --l3-firewall-rules
merakisync sync --verbose / --quiet
```

- CLI modules parse arguments and call library functions. No business logic in CLI.
- `cmd_sync.py` owns orchestration order (orgs → networks → devices → per-network resources).
- Errors must be logged clearly before exit. Never print a traceback as the only output.

---

## Configuration

Config file location (auto-selected):
- Regular user: `~/.config/merakisync/config.toml`
- Root: `/etc/merakisync/config.toml`
- Custom: set `XDG_CONFIG_HOME`

Environment variable overrides (always take precedence over the config file):

```
MERAKI_API_KEY
MERAKISYNC_DB_HOST
MERAKISYNC_DB_PORT
MERAKISYNC_DB_NAME
MERAKISYNC_DB_USER
MERAKISYNC_DB_PASSWORD
MERAKISYNC_LOG_LEVEL
```

---

## Database rules

- SQLAlchemy Core with raw `text()` queries. Not ORM declarative models.
- Alembic for all schema changes. No manual `CREATE TABLE` outside migrations.
- Default schema: `meraki`.
- `get_engine()` is `@lru_cache` — one engine per DSN per process. Do not create engines manually.
- Every SCD2 table must have a composite index on `(pk_columns..., active_to)`.
- Migration files are named `00NN_short_description.py` with sequential 4-digit IDs.
- Never modify a migration that has already been applied anywhere. Add a new one instead.

### Driver

Use `psycopg2-binary` and the `postgresql+psycopg2` driver string throughout. Do not use psycopg3 (`psycopg`) unless explicitly migrating.

---

## Adding a new model — quick reference

Full guide: `docs/adding-a-model.md`

Checklist:
1. Read the Meraki API docs. Record all camelCase field names.
2. Create `src/merakisync/models/<name>.py` following the pattern above.
3. Add to `models/__init__.py` and `src/merakisync/__init__.py`.
4. Write migration `src/merakisync/migrations/versions/00NN_add_<name>.py`.
5. Run `merakisync migrate`.
6. Add `--<name>` flag to `cli/cli.py` and `SyncFlags` in `cli/cmd_sync.py`.
7. Add orchestration call in `cmd_sync.py` at the right level (org/network/device).
8. Write tests in `tests/test_<name>.py`.

---

## Before writing code

**Every time a codebase change is requested**, before touching any file, you must respond with all of the following:

1. **Reasoning** — why this change is needed and what problem it solves.
2. **Assumptions** — any assumptions being made about intent, scope, or existing behaviour. Call out anything ambiguous and state how you are resolving it.
3. **Risks** — places where existing behaviour could break, subtle side effects, or anything that warrants extra care.
4. **Implementation plan** — a concrete, step-by-step list of every file that will change and what will be done to each one. Reference existing patterns from other models where applicable.

Do not write a single line of code until this pre-flight explanation is complete. If anything is unclear, ask before proceeding.

When writing code:
- Make incremental changes — one concern at a time.
- Do not refactor unrelated code while implementing a feature.
- Keep diffs small and reviewable.

---

## Definition of done

A feature or change is complete when:
- It works correctly for the intended use case.
- It does not break any existing model, sync, or retrieval behaviour.
- It follows the structure and patterns in this file.
- Edge cases are handled (empty API responses, missing fields, null values).
- Tests are written for any new `from_dashboard`, `from_row`, or field-mapping logic.

---

## What not to do

- Do not add `async` code. This is a sync tool running under cron/systemd.
- Do not introduce new dependencies without discussion.
- Do not add a plugin system, hook system, or event bus.
- Do not add caching layers inside the sync path (the DB is the cache).
- Do not silently swallow exceptions. Log and re-raise, or log and exit with a non-zero code.
- Do not import from `merakisync` inside model files (circular imports).
- Do not call `upsert()` in a loop — always use `upsert_many()`.
- Do not modify an applied migration file — create a new one.
- Do not put credentials or DSNs in source code.
- Do not add features that belong in `merakiops` (automation, remediation, scheduling).

---

## Reference

- Architecture overview: `docs/architecture.md`
- Adding a model: `docs/adding-a-model.md`
- Migrations: `docs/migrations.md`
- Testing: `docs/testing.md`
- Troubleshooting: `docs/troubleshooting.md`
