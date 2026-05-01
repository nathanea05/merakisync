# Adding a New Model

This guide walks through every step required to add a new Meraki resource type to merakisync. Follow it in order — each step depends on the previous one.

The example used throughout is a hypothetical `Vlan` model (MX appliance VLANs, retrieved from `GET /networks/{networkId}/appliance/vlans`).

---

## Step 1 — Read the Meraki API documentation

Before writing any code, look up the exact API response shape at [developer.cisco.com/meraki/api-v1](https://developer.cisco.com/meraki/api-v1/).

For each field, record:

- The **camelCase key** as returned by the API (e.g., `subnetMask`, `applianceIp`)
- The **Python type** you will use (`str`, `int`, `bool`, `list`, `dict`, or `None`-able versions)
- Whether the field is **always present** or **optional/nullable**
- Any **nested objects** that need to be flattened (like `Alert.network`)
- Any fields whose names **conflict with Python builtins** (`id`, `type`, `filter`, `list`, etc.)

Also note:

- What **endpoint** returns this resource and what **parameters** it requires
- Whether the resource has a **natural unique key** (a single stable ID, or a composite of two fields)
- Whether this resource represents a **current state** (use SCD2) or a **rolling metric** (use simple UPSERT — see `UplinkUsage` for reference)

---

## Step 2 — Create the model file

Create `src/merakisync/models/vlan.py`.

### 2a. Class variables

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, Type, TypeVar

from sqlalchemy import text

from merakisync.models.base import MerakiObj

logger = logging.getLogger(__name__)
I = TypeVar("I", bound="Vlan")


@dataclass(frozen=True, slots=True)
class Vlan(MerakiObj):
    """Meraki MX appliance VLAN — maps to meraki.vlan.

    Retrieved via GET /networks/{networkId}/appliance/vlans.
    network_id is injected before calling from_dashboard().
    """

    __table_name__: ClassVar[str] = "vlan"
    __pk__: ClassVar[tuple[str, ...]] = ("network_id", "vlan_id")
    __mapping_override__: ClassVar[dict[str, str]] = {
        "vlan_id": "id",          # "id" clashes with the base class default — remap it
        "appliance_ip": "applianceIp",
        "subnet_mask": "subnetMask",
    }
```

**Rules for class variables:**

- `__table_name__` — snake_case, singular noun, no schema prefix.
- `__pk__` — a tuple of snake_case column names. For resources with no stable single-column ID, use a composite key. Keep it as small as possible.
- `__mapping_override__` — only list fields that **cannot** be handled by automatic camelCase→snake_case conversion. If `camel_to_snake("applianceIp")` gives you `appliance_ip`, you do not need an override entry for it. Only add entries for: renamed fields, Python reserved words (`type` → `vlan_type`), injected fields that don't appear in the raw API response, or fields with irregular capitalisation.
- `__versioned__ = False` — add this only if the resource is a rolling metric that should be updated in place rather than versioned (see `UplinkUsage`).

### 2b. Business fields

List fields in this order:
1. Primary key fields (required, not None)
2. Other required / always-present fields
3. Optional / nullable fields (with `= None` default)
4. SCD2 versioning fields last (always optional)

```python
    # PK fields — required
    network_id: str        # injected
    vlan_id: int

    # Required fields
    name: str

    # Optional fields
    appliance_ip: str | None = None
    subnet: str | None = None
    subnet_mask: str | None = None
    fixed_ip_assignments: dict | None = None
    reserved_ip_ranges: list | None = None
    dns_nameservers: str | None = None
    dhcp_handling: str | None = None
    dhcp_lease_time: str | None = None
    dhcp_boot_options_enabled: bool | None = None

    # SCD2 versioning — always include for __versioned__ = True models
    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None
```

**Type guidance:**

- Use `dict | None` for nested JSON objects (e.g., `fixedIpAssignments`). The base class serialises these to JSON strings on write and deserialises for change comparison.
- Use `list | None` for JSON arrays.
- Do not try to model the internal structure of complex nested objects — store them as `dict` or `list` and let callers parse them if needed.
- Fields that the API always returns should not have `= None`. Fields that may be absent or null should have `= None`.

### 2c. Custom from_dashboard (only if needed)

Only override `from_dashboard` if the API response contains **nested objects that must be flattened** before the base class can map them. The base class handles flat dicts automatically.

```python
    @classmethod
    def from_dashboard(cls: Type[I], data: dict) -> I:
        flat = dict(data)
        # Example: inject network_id if the caller placed it in the raw dict
        # (often done in sync() before calling from_dashboard)
        return super().from_dashboard(flat)
```

See `Alert.from_dashboard()` for a real example of flattening a nested object.

### 2d. Implement get()

```python
    @classmethod
    def get(
        cls: Type[I],
        network_id: str,
        source: Literal["database", "meraki"] = "database",
        *,
        ts: datetime | Literal["all"] | None = None,
        vlan_id: int | None = None,
        name: str | None = None,
    ) -> list[I]:
        if ts and source == "meraki":
            raise ValueError("Timestamp lookups require source='database'.")

        if source == "meraki":
            from merakisync.dashboard import get_dashboard
            dashboard = get_dashboard()
            raw_vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
            vlans: list[I] = []
            for raw in raw_vlans:
                flat = dict(raw)
                flat["networkId"] = network_id   # inject
                vlan = cls.from_dashboard(flat)
                if vlan_id is not None and vlan.vlan_id != vlan_id:
                    continue
                if name and vlan.name != name:
                    continue
                vlans.append(vlan)
            return vlans

        if source == "database":
            from merakisync.database import get_engine
            engine = get_engine()
            where: list[str] = ["network_id = :network_id"]
            params: dict = {"network_id": network_id}

            if ts and ts != "all":
                where += ["active_from <= :ts", "(active_to > :ts OR active_to IS NULL)"]
                params["ts"] = ts
            elif ts != "all":
                where.append("active_to IS NULL")

            if vlan_id is not None:
                where.append("vlan_id = :vlan_id")
                params["vlan_id"] = vlan_id
            if name:
                where.append("name ILIKE :name")
                params["name"] = f"%{name}%"

            sql = text(
                f"SELECT * FROM {cls._qualified()} WHERE {' AND '.join(where)}"
                " ORDER BY vlan_id"
            )
            with engine.connect() as conn:
                rows = conn.execute(sql, params).mappings().all()
            return [cls.from_row(r) for r in rows]

        raise ValueError(f"Invalid source '{source}'. Must be 'database' or 'meraki'.")
```

**Rules for get():**

- Always guard `ts + source="meraki"` with a clear `ValueError`.
- Always use keyword-only arguments (`*`) for everything after `source`.
- Import `get_dashboard` and `get_engine` **inside** the if-branches, not at the top of the file. This prevents circular imports.
- Default `source` to `"database"` — callers reading from the DB is the common case.
- For DB queries, always add `active_to IS NULL` when `ts` is `None` so callers get current rows by default.

### 2e. Implement sync()

```python
    @classmethod
    def sync(cls: Type[I], network_id: str) -> list[I]:
        vlans = cls.get(network_id, source="meraki")
        if not vlans:
            logger.debug("No VLANs returned for network %s.", network_id)
            return []
        counts = cls.upsert_many(vlans)
        logger.debug("VLANs synced for network %s: %s", network_id, counts)
        return vlans
```

**Rules for sync():**

- Always use `upsert_many()`, never `upsert()` in a loop.
- Use `logger.debug` for per-resource messages that will repeat thousands of times. Use `logger.info` for org-level or summary messages.
- Return the list of objects so callers can inspect what was synced.

---

## Step 3 — Register the model

### 3a. models/\_\_init\_\_.py

Add to the imports and `__all__` list:

```python
from merakisync.models.vlan import Vlan

__all__ = [
    ...
    "Vlan",
]
```

### 3b. src/merakisync/\_\_init\_\_.py

Add the import and the `__all__` entry:

```python
from merakisync.models.vlan import Vlan

__all__ = [
    ...
    "Vlan",
]
```

---

## Step 4 — Write the migration

Create a new file in `src/merakisync/migrations/versions/`. Name it with the next revision number and a short description:

```
0002_add_vlan.py
```

Revision IDs are 4-digit strings: `0002`, `0003`, etc. Set `down_revision` to the ID of the previous migration.

```python
"""Add meraki.vlan table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-01
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vlan",
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("appliance_ip", sa.String(), nullable=True),
        sa.Column("subnet", sa.String(), nullable=True),
        sa.Column("subnet_mask", sa.String(), nullable=True),
        sa.Column("fixed_ip_assignments", sa.Text(), nullable=True),
        sa.Column("reserved_ip_ranges", sa.Text(), nullable=True),
        sa.Column("dns_nameservers", sa.String(), nullable=True),
        sa.Column("dhcp_handling", sa.String(), nullable=True),
        sa.Column("dhcp_lease_time", sa.String(), nullable=True),
        sa.Column("dhcp_boot_options_enabled", sa.Boolean(), nullable=True),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        schema="meraki",
    )
    op.create_index(
        "ix_vlan_pk_active",
        "vlan",
        ["network_id", "vlan_id", "active_to"],
        schema="meraki",
    )


def downgrade() -> None:
    op.drop_table("vlan", schema="meraki")
```

**Column type reference:**

| Python type | SQLAlchemy column type |
|---|---|
| `str` | `sa.String()` |
| `int` | `sa.Integer()` |
| `bool` | `sa.Boolean()` |
| `float` | `sa.Float()` |
| `dict` / `list` (JSON) | `sa.Text()` |
| `datetime` | `sa.DateTime(timezone=True)` |
| Large integers (bytes) | `sa.BigInteger()` |

**Index guidance:**

Every SCD2 table should have a composite index on `(pk_columns..., active_to)`. This index is used on every `SELECT` that filters for current rows.

**Apply the migration:**

```bash
merakisync migrate
```

---

## Step 5 — Wire up the CLI

### 5a. Add a sync flag — cli/cli.py

In the `sync` subparser section, add:

```python
sync_parser.add_argument(
    "--vlans", action="store_true", help="Sync MX appliance VLANs."
)
```

Then pass it to `SyncFlags`:

```python
flags = SyncFlags(
    ...
    vlans=args.vlans,
)
```

### 5b. Add the field to SyncFlags — cli/cmd_sync.py

```python
@dataclass
class SyncFlags:
    ...
    vlans: bool = False

    @property
    def sync_all(self) -> bool:
        return not any(vars(self).values())
```

### 5c. Add the orchestration call — cli/cmd_sync.py

Decide where in the sync order VLANs belong (VLANs are per-network, appliance networks only):

```python
from merakisync.models.vlan import Vlan

# inside the per-network loop:
if (do_all or flags.vlans) and "appliance" in product_types:
    logger.debug("    Syncing VLANs for network %s...", net_id)
    Vlan.sync(net_id)
```

---

## Step 6 — Write tests

Create `tests/test_vlan.py`. At minimum, test:

1. `from_dashboard` correctly maps known API fields.
2. `__mapping_override__` entries are applied (i.e., the `id` → `vlan_id` remap works).
3. `from_row` round-trips correctly from a dict.
4. `_data_fields()` excludes PK columns and versioning fields.
5. Any custom `from_dashboard` logic (nested object flattening, injected fields).

See `tests/test_models_base.py` for the test pattern — define a minimal concrete dataclass and test the methods on it.

---

## Checklist

Use this to verify you have not missed anything before committing.

```
[ ] API fields documented (endpoint, required params, all camelCase keys)
[ ] models/vlan.py created
    [ ] __table_name__ set
    [ ] __pk__ set
    [ ] __mapping_override__ only contains non-trivial overrides
    [ ] __versioned__ = False added if this is a metric table
    [ ] All PK fields listed first and not Optional
    [ ] All SCD2 models have active_from, active_to, last_seen fields
    [ ] get() imports get_dashboard / get_engine inside the if-branch
    [ ] get() returns list[I], not list[I] | None
    [ ] sync() uses upsert_many(), not upsert() in a loop
[ ] models/__init__.py updated
[ ] src/merakisync/__init__.py updated
[ ] migrations/versions/00NN_add_vlan.py created
    [ ] down_revision points to the previous migration
    [ ] All columns present (including active_from/to/last_seen for SCD2)
    [ ] Index on (pk_cols..., active_to) created
[ ] merakisync migrate run and confirmed
[ ] cli/cli.py: --vlans flag added to sync subparser
[ ] cli/cmd_sync.py: vlans field added to SyncFlags, orchestration call added
[ ] tests/test_vlan.py written
```
