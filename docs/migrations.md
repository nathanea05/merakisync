# Database Migrations

merakisync uses [Alembic](https://alembic.sqlalchemy.org/) to manage its database schema. This document explains how to create, apply, test, and roll back migrations as the schema evolves.

---

## How Alembic is configured

`alembic.ini` at the project root points Alembic to the migrations directory:

```ini
script_location = src/merakisync/migrations
```

The DSN (database connection string) is **not** stored in `alembic.ini`. It is injected at runtime by `src/merakisync/migrations/env.py`, which calls `merakisync.config.get_config()`. This means migrations always connect to whichever database is configured for the current user — no separate Alembic URL to maintain.

---

## Applying migrations

To upgrade the database to the latest revision:

```bash
merakisync migrate
```

This is equivalent to running `alembic upgrade head` from the project root. It is safe to run multiple times — Alembic records which revisions have already been applied in the `alembic_version` table and skips them.

To run migrations directly via the Alembic CLI (useful for debugging):

```bash
cd /path/to/merakisync
alembic upgrade head
```

---

## Checking migration status

```bash
# Show the current revision applied to the database
alembic current

# Show the full revision history
alembic history --verbose

# Show pending revisions (not yet applied)
alembic history -r current:head
```

---

## Creating a new migration

### When to create one

Create a migration whenever you:

- Add a new model (new table)
- Add a new field to an existing model (new column)
- Remove a field from a model (drop a column)
- Change a field's type
- Add or remove an index

Do not create a migration for changes that don't touch the database schema (e.g., adding a filter parameter to `get()`, changing sync logic).

### Naming convention

Migration files live in `src/merakisync/migrations/versions/`. Use the format:

```
00NN_short_description.py
```

Where `NN` is the next sequential number, zero-padded to four digits. Examples:

```
0001_initial_schema.py
0002_add_vlan.py
0003_add_device_config_hash.py
0004_drop_alert_dismissed_at.py
```

Alembic does not require this naming convention — it uses the `revision` variable inside the file to build the chain — but consistent names make the history readable.

### Writing the migration file

Copy this template and fill it in:

```python
"""Short description of the change.

Revision ID: 00NN
Revises: 00NN-1
Create Date: YYYY-MM-DD
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "00NN"
down_revision: Union[str, None] = "00NN-1"   # ID of the previous migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schema changes to apply
    pass


def downgrade() -> None:
    # How to reverse the upgrade
    pass
```

**`down_revision` must be set correctly.** Alembic builds a linked list of revisions. If `down_revision` is wrong, the migration chain breaks and Alembic will refuse to run.

---

## Common migration patterns

### Add a new table

```python
def upgrade() -> None:
    op.create_table(
        "vlan",
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
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

### Add a column to an existing table

```python
def upgrade() -> None:
    op.add_column(
        "device",
        sa.Column("config_hash", sa.String(), nullable=True),
        schema="meraki",
    )

def downgrade() -> None:
    op.drop_column("device", "config_hash", schema="meraki")
```

New columns must be `nullable=True` unless you also provide a `server_default`, because existing rows will have no value for the new column.

### Drop a column

```python
def upgrade() -> None:
    op.drop_column("alert", "dismissed_at", schema="meraki")

def downgrade() -> None:
    op.add_column(
        "alert",
        sa.Column("dismissed_at", sa.String(), nullable=True),
        schema="meraki",
    )
```

Always write a working `downgrade()` so the migration can be rolled back cleanly.

### Add an index

```python
def upgrade() -> None:
    op.create_index(
        "ix_device_model",
        "device",
        ["model"],
        schema="meraki",
    )

def downgrade() -> None:
    op.drop_index("ix_device_model", table_name="device", schema="meraki")
```

### Rename a column

```python
def upgrade() -> None:
    op.alter_column("uplink", "ip_asigned_by", new_column_name="ip_assigned_by", schema="meraki")

def downgrade() -> None:
    op.alter_column("uplink", "ip_assigned_by", new_column_name="ip_asigned_by", schema="meraki")
```

---

## Rolling back a migration

To undo the most recent migration:

```bash
alembic downgrade -1
```

To roll back to a specific revision:

```bash
alembic downgrade 0001
```

To undo all migrations (back to an empty schema):

```bash
alembic downgrade base
```

> **Production warning:** Rolling back a migration that dropped a table or column will attempt to recreate it, but any data that was in that table or column is gone. Always take a database backup before running destructive migrations in production.

---

## Keeping the Python model and migration in sync

The migration file and the model dataclass must always agree on column names and types. The most common mistake is forgetting to update one when changing the other.

When you add a field to a model:
1. Add the `Column` definition to the migration's `upgrade()`.
2. Add the reverse `drop_column` to `downgrade()`.
3. Apply the migration: `merakisync migrate`.

When you remove a field from a model:
1. Remove the field from the dataclass.
2. Add a `drop_column` to the migration's `upgrade()`.
3. Add an `add_column` to `downgrade()`.

**Do not modify an existing migration that has already been applied to any database.** Once a migration is in version control and applied anywhere, treat it as immutable. Instead, create a new migration that makes the additional change.

---

## Testing migrations locally

Before applying a migration to a shared environment, test it against a local or development database:

```bash
# Apply
alembic upgrade head

# Confirm it worked
alembic current

# Roll back
alembic downgrade -1

# Confirm the rollback worked
alembic current

# Re-apply
alembic upgrade head
```

If either `upgrade` or `downgrade` raises an error, fix the migration file before committing it.

---

## Squashing migrations (future)

Over time, the migrations directory will grow. Once a baseline database version is established that all deployments are guaranteed to be on or past, old migrations can be squashed into a single new initial migration. This is not needed now, but document it when the directory exceeds ~20 files.
