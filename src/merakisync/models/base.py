from __future__ import annotations

import json
import logging
from dataclasses import fields as dataclass_fields, is_dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Sequence, Type, TypeVar

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from merakisync.utils.casing import camel_to_snake, snake_to_camel

logger = logging.getLogger(__name__)

I = TypeVar("I", bound="MerakiObj")

# Fields that hold SCD2 bookkeeping timestamps and must never be used when
# comparing whether the business data on a row has changed.
_VERSIONING_FIELDS: frozenset[str] = frozenset({"active_from", "active_to", "last_seen"})


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _db_value(value: Any) -> Any:
    """Coerce Python dicts/lists to JSON strings for storage."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


class MerakiObj:
    """Base class for all Meraki resource objects.

    Child classes must be dataclasses and should set:
        __table_name__         str   — database table name
        __pk__                 tuple — primary key column names (snake_case)
        __schema__             str   — database schema  (default: "meraki")
        __mapping_override__   dict  — {model_field: dashboard_key} for fields
                                       that do not follow camelCase conversion
        __versioned__          bool  — False to use simple UPSERT instead of SCD2
    """

    __schema__: ClassVar[str] = "meraki"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __table_name__: ClassVar[str] = ""
    __mapping_override__: ClassVar[dict[str, str]] = {}
    __versioned__: ClassVar[bool] = True  # SCD2 by default

    # ------------------------------------------------------------------
    # Change tracking
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Called by the dataclass-generated __init__ after all fields are set."""
        self._changed_fields: set[str] = set()

    def __setattr__(self, name: str, value: Any) -> None:
        # Track post-init assignments. During __init__, _changed_fields does not
        # yet exist in __dict__, so we skip tracking until it is initialised.
        if "_changed_fields" in self.__dict__:
            if name in self.__class__.__pk__:
                raise AttributeError(
                    f"{self.__class__.__name__}.{name} is a primary key field and cannot be reassigned."
                )
            if name != "_changed_fields":
                self._changed_fields.add(name)
        object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    # Class-level naming helpers
    # ------------------------------------------------------------------

    @classmethod
    def _table_name(cls) -> str:
        return cls.__table_name__ or camel_to_snake(cls.__name__)

    @classmethod
    def _qualified(cls) -> str:
        return f"{cls.__schema__}.{cls._table_name()}"

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_dashboard(cls: Type[I], data: dict[str, Any]) -> I:
        """Convert a camelCase Meraki API response dict into a model instance.

        Applies __mapping_override__ first, then falls back to camel_to_snake
        for any key not explicitly mapped.  Fields not present on the dataclass
        are silently ignored.
        """
        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a dataclass")

        field_names = {f.name for f in dataclass_fields(cls)}

        # Invert the override map: dashboard_key -> model_field
        key_to_field: dict[str, str] = {
            dashboard_key: model_field
            for model_field, dashboard_key in cls.__mapping_override__.items()
        }

        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            attr = key_to_field.get(key) or camel_to_snake(key)
            if attr in field_names:
                kwargs[attr] = value

        return cls(**kwargs)

    @classmethod
    def from_row(cls: Type[I], row: Any) -> I:
        """Convert a SQLAlchemy row (or dict) into a model instance.

        Column names in the query must already be snake_case and match the
        dataclass field names.
        """
        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a dataclass")

        field_names = {f.name for f in dataclass_fields(cls)}

        if isinstance(row, dict):
            data: dict[str, Any] = row
        elif hasattr(row, "_mapping"):
            data = dict(row._mapping)
        else:
            data = dict(row)

        kwargs = {k: v for k, v in data.items() if k in field_names}
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        if not is_dataclass(self):
            raise TypeError(f"{self.__class__.__name__} must be a dataclass")
        return {f.name: getattr(self, f.name) for f in dataclass_fields(self)}

    def _data_fields(self) -> dict[str, Any]:
        """Return only the business-data fields (excludes PK and versioning)."""
        cls = self.__class__
        excluded = set(cls.__pk__) | _VERSIONING_FIELDS
        return {
            f.name: getattr(self, f.name)
            for f in dataclass_fields(self)  # type: ignore[arg-type]
            if f.name not in excluded
        }

    def to_meraki_dict(self, fields: list[str] | None = None) -> dict[str, Any]:
        """Return a camelCase dict suitable for sending to the Meraki API.

        Excludes SCD2 versioning fields (active_from, active_to, last_seen).
        Uses __mapping_override__ for fields that do not follow snake_to_camel.

        Args:
            fields: Optional list of snake_case field names to include.
                    When omitted, all non-versioning fields are included.
        """
        if not is_dataclass(self):
            raise TypeError(f"{self.__class__.__name__} must be a dataclass")
        cls = self.__class__
        override = cls.__mapping_override__  # {model_field: api_key}
        result: dict[str, Any] = {}
        for f in dataclass_fields(self):
            name = f.name
            if name in _VERSIONING_FIELDS:
                continue
            if fields is not None and name not in fields:
                continue
            api_key = override.get(name) or snake_to_camel(name)
            result[api_key] = getattr(self, name)
        return result

    # ------------------------------------------------------------------
    # Single-row upsert
    # ------------------------------------------------------------------

    def upsert(self, engine: Engine | None = None) -> str:
        """Persist this object to the database.

        For SCD2 models (__versioned__ = True):
            - No current row → INSERT (active_from=now, active_to=NULL, last_seen=now)
            - Current row exists, data unchanged → UPDATE last_seen only
            - Current row exists, data changed → expire old row, INSERT new row

        For simple models (__versioned__ = False):
            - INSERT … ON CONFLICT (pk) DO UPDATE SET <all non-pk columns>

        Returns "inserted", "updated", or "expired+inserted".
        """
        if engine is None:
            from merakisync.database import get_engine
            engine = get_engine()

        with engine.connect() as conn:
            result = self._upsert_with_conn(conn)
            conn.commit()
        return result

    def _upsert_with_conn(self, conn: Connection) -> str:
        """Execute the upsert inside an already-open connection."""
        cls = self.__class__

        if not is_dataclass(self):
            raise TypeError(f"{cls.__name__} must be a dataclass")
        if not cls.__pk__:
            raise ValueError(f"{cls.__name__} must define __pk__")

        row = self.to_dict()
        missing = [col for col in cls.__pk__ if col not in row or row[col] is None]
        if missing:
            raise ValueError(f"{cls.__name__} missing required PK field(s): {missing}")

        if cls.__versioned__:
            return self._scd2_upsert(conn, row)
        else:
            return self._simple_upsert(conn, row)

    # ------------------------------------------------------------------
    # SCD2 logic
    # ------------------------------------------------------------------

    def _scd2_upsert(self, conn: Connection, row: dict[str, Any]) -> str:
        cls = self.__class__
        now = _now()

        pk_where, pk_params = _build_pk_where(cls.__pk__, row)
        active_where = f"{pk_where} AND active_to IS NULL"

        existing = conn.execute(
            text(f"SELECT * FROM {cls._qualified()} WHERE {active_where} LIMIT 1"),
            pk_params,
        ).mappings().first()

        if existing is None:
            _insert_row(conn, cls._qualified(), row, active_from=now, last_seen=now)
            return "inserted"

        # Compare business data only (no PK, no timestamps)
        current_data = {
            k: v for k, v in dict(existing).items()
            if k not in set(cls.__pk__) | _VERSIONING_FIELDS
        }
        new_data = self._data_fields()

        if _data_equal(current_data, new_data):
            conn.execute(
                text(f"UPDATE {cls._qualified()} SET last_seen = :ts WHERE {active_where}"),
                {**pk_params, "ts": now},
            )
            return "updated"

        # Data changed: expire old row, insert new one
        conn.execute(
            text(f"UPDATE {cls._qualified()} SET active_to = :ts WHERE {active_where}"),
            {**pk_params, "ts": now},
        )
        _insert_row(conn, cls._qualified(), row, active_from=now, last_seen=now)
        return "expired+inserted"

    # ------------------------------------------------------------------
    # Simple UPSERT (no versioning)
    # ------------------------------------------------------------------

    def _simple_upsert(self, conn: Connection, row: dict[str, Any]) -> str:
        cls = self.__class__
        now = _now()

        non_pk = [col for col in row if col not in set(cls.__pk__) | _VERSIONING_FIELDS]
        # Use last_seen from the object if explicitly set, otherwise default to now.
        last_seen = row["last_seen"] if row.get("last_seen") is not None else now
        all_cols = list(cls.__pk__) + non_pk + ["last_seen"]

        col_list = ", ".join(all_cols)
        val_list = ", ".join(f":{c}" for c in all_cols)
        pk_list = ", ".join(cls.__pk__)
        update_clause = ", ".join(
            f"{c} = EXCLUDED.{c}" for c in non_pk
        ) + ", last_seen = EXCLUDED.last_seen"

        params = {c: _db_value(row.get(c)) for c in list(cls.__pk__) + non_pk}
        params["last_seen"] = last_seen

        conn.execute(
            text(
                f"INSERT INTO {cls._qualified()} ({col_list})"
                f" VALUES ({val_list})"
                f" ON CONFLICT ({pk_list})"
                f" DO UPDATE SET {update_clause}"
            ),
            params,
        )
        return "upserted"

    # ------------------------------------------------------------------
    # Batch upsert
    # ------------------------------------------------------------------

    @classmethod
    def upsert_many(
        cls,
        rows: Sequence[MerakiObj],
        engine: Engine | None = None,
    ) -> dict[str, int]:
        """Upsert a sequence of objects in a single connection and transaction.

        This is far more efficient than calling .upsert() per row because it
        avoids opening a new database connection for every object.

        Returns:
            A dict with counts: {"inserted": N, "updated": N, "expired+inserted": N,
                                  "upserted": N}
        """
        if not rows:
            return {}

        if engine is None:
            from merakisync.database import get_engine
            engine = get_engine()

        counts: dict[str, int] = {}
        with engine.connect() as conn:
            for obj in rows:
                result = obj._upsert_with_conn(conn)
                counts[result] = counts.get(result, 0) + 1
            conn.commit()

        return counts


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_pk_where(
    pk_cols: tuple[str, ...], row: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Return (WHERE clause string, params dict) for the given PK columns."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for col in pk_cols:
        val = row[col]
        if val is None:
            clauses.append(f"{col} IS NULL")
        else:
            clauses.append(f"{col} = :pk_{col}")
            params[f"pk_{col}"] = val
    return " AND ".join(clauses), params


def _insert_row(
    conn: Connection,
    qualified_table: str,
    row: dict[str, Any],
    *,
    active_from: datetime,
    last_seen: datetime,
) -> None:
    """INSERT a full row, injecting SCD2 timestamp values."""
    data = {k: _db_value(v) for k, v in row.items() if k not in _VERSIONING_FIELDS}
    data["active_from"] = active_from
    data["active_to"] = None
    data["last_seen"] = last_seen

    col_list = ", ".join(data.keys())
    val_list = ", ".join(f":{k}" for k in data.keys())
    conn.execute(
        text(f"INSERT INTO {qualified_table} ({col_list}) VALUES ({val_list})"),
        data,
    )


def _data_equal(existing: dict[str, Any], new: dict[str, Any]) -> bool:
    """Compare two business-data dicts, normalising JSON blobs for comparison."""
    if set(existing.keys()) != set(new.keys()):
        return False
    for key in existing:
        ev = existing[key]
        nv = new[key]
        # Rows from DB return JSON strings; Python objects may be dicts/lists
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except (json.JSONDecodeError, TypeError):
                pass
        if ev != nv:
            return False
    return True
