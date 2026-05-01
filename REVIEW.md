# REVIEW.md

## Purpose

This file defines the self-review process that must be completed before any code is considered done.

The goal is to ensure all changes to merakisync are:
- Correct
- Safe
- Scalable
- Maintainable
- Consistent with project architecture

No code should be finalized without passing this review.

---

## Review Process (Required)

Before completing any task, walk through every section below and explicitly confirm each item.

If any answer is "no" or "uncertain", fix it before proceeding.

---

## 1. Scope & Intent Check

- Does this change strictly align with the purpose of merakisync?
  - Sync Meraki → PostgreSQL
  - Retrieve objects from API or DB
- Am I introducing unrelated functionality (alerting, remediation, scheduling, UI, etc.)?
  - If yes → STOP and remove it
- Is this solving the actual problem, or am I overengineering?

---

## 2. Architecture Compliance

- Does this change respect separation of concerns?

| Concern | Lives in |
|---|---|
| Meraki API calls | `Model.get(source="meraki")` / `Model.sync()` |
| Database queries | `Model.get(source="database")`, `MerakiObj.upsert*` |
| Per-resource sync logic | `Model.sync()` |
| Sync orchestration (order, which networks get which resources) | `cli/cmd_sync.py` |
| CLI argument parsing and dispatch | `cli/cli.py` |
| All custom exceptions | `exceptions.py` |
| Credentials / secrets | config file or env vars only |

- Did I accidentally mix responsibilities across layers?
- Are modules still small and focused?

---

## 3. Data Flow Integrity

Does all data follow one of these two paths and no other?

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

- Did I bypass `from_dashboard()` or `from_row()` and pass raw dicts to callers?
- Did I call `upsert()` in a loop instead of using `upsert_many()`?
  - `upsert_many()` uses a single connection and one transaction. `upsert()` in a loop does not. Always use `upsert_many()` when syncing a collection.

---

## 4. Versioning (CRITICAL)

For any SCD2 model (`__versioned__ = True`, which is the default):

- Does the table include `active_from`, `active_to`, and `last_seen` columns?
- Does `upsert_many()` correctly:
  - Detect meaningful changes (business-data fields only — PK and versioning columns excluded)
  - Expire old records (`active_to = now()`) when data changes
  - Insert a new record when data changes (`active_from = now(), active_to = NULL`)
  - Update `last_seen` only when data is unchanged
- Is there **ever** more than one active row (`active_to IS NULL`) for a unique object?
  - If yes → BUG
- Does the composite index on `(pk_columns..., active_to)` exist in the migration?

For `__versioned__ = False` models (currently only `UplinkUsage`):
- Is this actually a rolling metric, not a configuration state?
- Does it use `INSERT … ON CONFLICT DO UPDATE` (not SCD2)?
- Does it have `last_seen` but no `active_from` / `active_to`?

---

## 5. Data Modeling

- Are all attribute names `snake_case`?
- Does each model map 1:1 to database columns?
- Is `camelCase → snake_case` conversion handled by `camel_to_snake()` in the base class?
- Does `__mapping_override__` only contain entries that `camel_to_snake()` cannot handle automatically?
  - Python reserved words (`type` → `alert_type`)
  - Injected fields that don't appear in the raw API response
  - Irregular capitalisation that `camel_to_snake()` gets wrong
  - Do not add entries for fields `camel_to_snake()` already handles correctly
- Are composite PKs handled correctly?
  - Switchport: `(serial, port_id)`
  - Uplink: `(network_id, serial, interface)`
  - UplinkUsage: `(network_id, serial, interface, month, year)`
  - L3FirewallRule: `(network_id, rule_order)`

---

## 6. `get()` Behaviour

- Does `.get()` support both `source="database"` and `source="meraki"`? (Not `"db"` or `"dashboard"` — those are wrong values and will fall through to the `raise ValueError` at the bottom.)
- Are API and DB retrieval paths clearly separated inside the method?
- Does it return typed model instances, not raw dicts?
- Does `get(source="database")` default to current rows only (`active_to IS NULL`) when `ts` is `None`?
- Does it raise `ValueError` if `ts` is used with `source="meraki"`?
- Are `get_dashboard` and `get_engine` imported **inside** the if-branch, not at the top of the file?
- Does it return `list[I]`, not `list[I] | None`? (Return an empty list, never `None`.)

---

## 7. CLI Review

- Is the CLI thin — no business logic, only argument parsing and dispatch?
- Does `cli/cmd_sync.py` orchestrate by calling `Model.sync()` — not by reimplementing sync logic?
- Are commands predictable and scriptable?
- Are flags consistent with the existing pattern (`--organizations`, `--networks`, `--devices`, `--switchports`, etc.)?
- Are errors logged clearly before exit? (No bare tracebacks as the only output.)

---

## 8. Database & Migrations

- Is every schema change reflected in a new Alembic migration file in `src/merakisync/migrations/versions/`?
- Is the migration file named with the next sequential 4-digit ID (`00NN_short_description.py`)?
- Is `down_revision` set to the correct previous revision ID?
- Does `upgrade()` have a working `downgrade()` that reverses it cleanly?
- Does this work on a fresh database (i.e., does it not assume pre-existing state beyond what migrations create)?
- Does the schema default to `meraki` unless explicitly overridden?
- Were raw `text()` queries used (SQLAlchemy Core), not ORM declarative models?
- Was an applied migration modified instead of a new one created?
  - If yes → STOP. Applied migrations are immutable. Create a new one.

---

## 9. Performance & Scale

Think at scale:

- Will this work with thousands of networks and tens of thousands of devices?
- Am I making unnecessary API calls (e.g., re-fetching data already in scope)?
- Am I introducing N+1 query problems (e.g., one DB query per object instead of one query for all)?
- Did I use `upsert_many()` instead of `upsert()` in a loop?
- Can this be run repeatedly under cron/systemd without creating duplicates or accumulating bad state?

---

## 10. Error Handling & Logging

- Are errors visible, actionable, and not silently swallowed?
  - Log and re-raise, or log and exit with a non-zero code. Never `except Exception: pass`.
- Is logging at the right level?
  - `logger.debug` for per-resource messages that repeat thousands of times
  - `logger.info` for org-level or summary messages
  - `logger.warning` / `logger.error` for degraded or failed operations
- Are all custom exceptions defined in `exceptions.py` and nowhere else?

---

## 11. Configuration

- Does this respect centralised config loaded by `get_config()`?
- Does it avoid requiring users to re-enter API keys or DB credentials for each call?
- Are environment variable overrides supported and respected?
  - `MERAKI_API_KEY`, `MERAKISYNC_DB_HOST`, `MERAKISYNC_DB_PORT`, `MERAKISYNC_DB_NAME`, `MERAKISYNC_DB_USER`, `MERAKISYNC_DB_PASSWORD`, `MERAKISYNC_LOG_LEVEL`
- Are credentials or DSNs hardcoded anywhere in source?
  - If yes → STOP and remove them.

---

## 12. Code Quality

- Are type hints present and correct?
- Are function names clear and consistent with the rest of the codebase?
- Did I avoid unnecessary abstractions (no `__init_subclass__`, dynamic class factories, or class decorators)?
- Did I avoid `async` code? (This is a sync tool running under cron/systemd. No async.)
- Did I introduce a new dependency without discussion?

---

## 13. Circular Import Check

- Do any model files import from `merakisync` (the package root)?
  - If yes → BUG. The package root imports from models; importing back creates a circular dependency.
- Do model files import `get_dashboard` and `get_engine` **inside** the method body (deferred), not at the top of the file?

```python
# WRONG — causes a circular import at module load time
from merakisync import get_dashboard, get_engine

# CORRECT — deferred import inside the method body
def get(cls, ...):
    if source == "meraki":
        from merakisync.dashboard import get_dashboard
        ...
    if source == "database":
        from merakisync.database import get_engine
        ...
```

---

## 14. Regression Check

- Did I break any existing model, sync, or retrieval behaviour?
- Did I change behaviour without documenting it?
- Would this surprise another engineer reading the code?

---

## 15. Simplicity Check

Ask yourself:

- Is there a simpler way to do this?
- Did I introduce abstraction before it was needed?
- Would a mid-level engineer understand this quickly without explanation?

If not → simplify.

---

## 16. Real-World Test

Mentally simulate:

- Running `merakisync sync` across 300+ networks
- Running via cron every 5 minutes
- Debugging a failure at 2am with only logs available

Ask:

- Would this be easy to debug?
- Would failures be obvious and actionable?
- Would it behave predictably on every run?

---

## Final Checklist

Before marking complete:

- [ ] All sections reviewed
- [ ] No architectural violations
- [ ] Versioning is correct (SCD2 or explicit opt-out)
- [ ] `upsert_many()` used — never `upsert()` in a loop
- [ ] Correct `source` values used (`"database"` / `"meraki"`)
- [ ] No circular imports introduced
- [ ] Migration written for any schema change
- [ ] No unnecessary complexity

---

## Final Rule

If something feels "clever" or "fancy":

> It is probably wrong.

Choose the simplest solution that works at scale.
