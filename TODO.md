# merakisync — audit TODO

Issues found during a full codebase audit. Ordered by priority within each tier.

---

## Tier 1 — Fix before next release (bugs / broken behavior)

### 1. Duplicate `MerakiConnectionError` breaks `merakisync init` API key validation

**Files:** `src/merakisync/dashboard.py:13`, `src/merakisync/exceptions.py:12`, `src/merakisync/cli/cmd_init.py:48`

`dashboard.py` defines its own local `MerakiConnectionError`. `exceptions.py` defines a separate, unrelated class with the same name. `cmd_init.py` imports from `exceptions.py` — so the `except MerakiConnectionError` block at line 48 never catches the exception raised by `validate_api_key()`. An invalid API key during `merakisync init` produces an uncaught traceback instead of `"FAIL <message>"`.

**Fix:** Remove `class MerakiConnectionError` from `dashboard.py`. Import and raise `merakisync.exceptions.MerakiConnectionError` instead.

---

### 2. JSONB operators used on TEXT columns — tag filters fail at runtime

**Files:** `src/merakisync/models/network.py:144-149`, `src/merakisync/models/device.py:164-169`

`Network.get(source="database", tags_include=[...])` and the equivalent `Device.get()` call use `?&` and `?|` (PostgreSQL JSONB containment operators) against the `tags` column, which is stored as `sa.Text()`. PostgreSQL will raise `operator does not exist: text ?& text[]` at runtime.

**Fix:** Either (a) migrate `tags` (and `product_types`) to JSONB columns, or (b) replace the JSONB operators with a text-based fallback such as `tags::jsonb ?& :tags_include`.

---

### 3. `DhcpServerPolicy.sync()` calls `upsert()` instead of `upsert_many()`

**File:** `src/merakisync/models/dhcp_server_policy.py:114`

`policy.upsert()` — spec rule: *"Always call `upsert_many()`, never `upsert()` in a loop."* This applies even for single objects.

**Fix:** `cls.upsert_many([policy])`

---

### 4. `DhcpServerPolicy.get()` and `sync()` return `I | None`, not `list[I]`

**File:** `src/merakisync/models/dhcp_server_policy.py:63, 107`

Every other model's `get()` returns `list[I]` and an empty list when nothing is found. `DhcpServerPolicy` breaks this contract, making it impossible to treat uniformly with other models.

**Fix:** Change return type to `list[I]`. Return `[]` when no record is found. Update `sync()` to return `list[I]` and wrap the single result in a list before passing to `upsert_many()`.

---

## Tier 2 — Fix soon (silent wrong behavior)

### 5. `Device.get()` silently drops `product_types_exclude`

**File:** `src/merakisync/models/device.py`

`product_types_exclude` is accepted and documented but never applied — neither in the `source="meraki"` path nor the `source="database"` path. Callers get back excluded types with no error.

**Fix:** Apply client-side exclusion after the API response (meraki path) and add a WHERE clause in the database path (using model prefix matching, consistent with `product_types_include`).

---

### 6. `Network.get()` silently drops `product_types_include/exclude` in the database path

**File:** `src/merakisync/models/network.py`

These two parameters are applied client-side for `source="meraki"` but there is no corresponding filter in the `source="database"` branch. Querying the database with these filters silently returns all networks.

**Fix:** Add `product_types` filtering in the DB path. Since `product_types` is a JSON array stored as text, this likely requires a cast (`product_types::jsonb ?& :pt_include`) or a migration to JSONB (see issue #2).

---

### 7. `name` filter semantics differ between sources, and this is undocumented

**Files:** `organization.py`, `network.py`, `device.py`, `vlan.py`

For `source="meraki"`: exact case-insensitive match.
For `source="database"`: ILIKE substring match (`%name%`).

This inconsistency is not documented in any `get()` docstring. A caller filtering by name gets different result sets depending on source.

**Fix:** Document the difference explicitly in each `get()` docstring. Consider normalising to exact-match in both paths, or making the DB path do exact match by default and accepting a separate `name_contains` parameter for substring search.

---

## Tier 3 — Clean up (technical debt / spec alignment)

### 8. `_changed_fields` is undocumented public infrastructure

**File:** `src/merakisync/models/base.py`

`_changed_fields` is populated by `MerakiObj.__setattr__` after construction. It is intentionally part of the public API — external callers (specifically merakiops) read this set to determine which fields changed and build Meraki action batches from them. It is currently undocumented, making it look like dead code to future maintainers.

**Fix:** Add a clear docstring to the `__post_init__` / `__setattr__` block explaining that `_changed_fields` is a public, stable interface for external callers doing partial API writes. Note that merakisync itself does not consume it.

---

### 9. Models use `@dataclass()`, not `@dataclass(frozen=True, slots=True)` as specified

**Files:** All model files

CLAUDE.md's model template shows `@dataclass(frozen=True, slots=True)`. All models use plain `@dataclass()`. This is not accidental — `frozen=True` is incompatible with the `_changed_fields` / `__setattr__` mechanism (see issue #8). The spec and base class are in conflict.

**Fix:** Update CLAUDE.md to reflect the actual design: models are intentionally mutable (unfrozen) to support change tracking for external callers. Remove the `frozen=True, slots=True` from the template.

---

### 10. `dashboard.py` violates the exception boundary rule

**File:** `src/merakisync/dashboard.py:13`

Covered by issue #1. Even after the bug fix, the fact that `dashboard.py` ever defined its own exception class is a spec violation: *"All custom exceptions. The only place they are defined" = `exceptions.py`.*

Resolved as part of fixing issue #1.

---

### 11. `__mapping_override__` bloat — unnecessary entries in multiple models

The spec says: *"Only add entries for fields that cannot be handled by automatic `camel_to_snake` conversion: Python reserved words, injected fields, or irregular capitalisation."*

Models with unnecessary entries (all of these convert correctly without overrides):

- **`Switchport`** (`src/merakisync/models/switchport.py:31-42`) — all 9 entries: `poeEnabled`, `rstpEnabled`, `stpGuard`, `voiceVlan`, `allowedVlans`, `linkNegotiation`, `accessPolicyType`, `stickyMacAllowList`, `stickyMacAllowListLimit`
- **`Alert`** (`src/merakisync/models/alert.py:37-45`) — `startedAt`, `resolvedAt`, `dismissedAt`, `deviceType`, `categoryType`
- **`Uplink`** (`src/merakisync/models/uplink.py:29-32`) — `ip_assigned_by: "ipAssignedBy"` (CLAUDE.md itself uses this as an example of what NOT to include)
- **`L3FirewallRule`** (`src/merakisync/models/l3_firewall_rule.py:39-47`) — `destPort`, `destCidr`, `srcPort`, `srcCidr`, `syslogEnabled`

Note: `portId → port_id` (Switchport), `networkId → network_id` and `ruleOrder → rule_order` (L3FirewallRule) are injected fields — those entries are legitimate per spec.

**Fix:** Remove the unnecessary entries. No behavior changes since `camel_to_snake` already handles them identically.

---

## Tier 4 — Minor / cosmetic

### 12. `UplinkUsage.sync()` gap warning message is misleading

**File:** `src/merakisync/models/uplink_usage.py:211-218`

The warning says data "is unrecoverable" — but the code then queries and partially recovers it. The truly unrecoverable threshold is the API's 30-day absolute lookback, not 14 days. The 14-day limit is per-query, not a hard data boundary. The format argument order in the log call is also confusing (later date printed before earlier date).

**Fix:** Reword the warning to accurately describe what happens: that a gap was detected, that only 14 days can be recovered per sync, and that a subsequent sync will cover the remainder. Flip the date arguments to chronological order.

---

### 13. `Optional[str|None]` in `dashboard.py`

**File:** `src/merakisync/dashboard.py:63`

`Optional[str|None]` is equivalent to `str | None` — the `Optional` wrapper is redundant.

**Fix:** Change to `api_key: str | None = None`.

---

### 14. Migration 0008 docstring has wrong `Revises` field

**File:** `src/merakisync/migrations/versions/0008_add_ssid_psk.py:5`

The header comment says `Revises: 0008` — should be `Revises: 0007`. The actual `down_revision = "0007"` is correct. Cosmetic only.

**Fix:** Change the comment to `Revises: 0007`.

---

## Completed

### 1. Duplicate `MerakiConnectionError` breaks `merakisync init` API key validation
Removed the local `class MerakiConnectionError` from `dashboard.py`. Now imports from `merakisync.exceptions`. Also removed the redundant `Optional` import and fixed `Optional[str|None]` → `str | None` on `get_dashboard` (issue #13).

### 2. JSONB operators used on TEXT columns — tag filters fail at runtime
### 6. `Network.get()` silently drops `product_types_include/exclude` in the database path
Migration `0009_jsonb_tags_product_types.py` converts `network.tags`, `network.product_types`, and `device.tags` from TEXT to JSONB. Added `product_types ?& / ?|` filtering to `Network.get()` DB path.
