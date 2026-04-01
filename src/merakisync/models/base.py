from __future__ import annotations

from typing import ClassVar, TypeVar, Any, Type
from dataclasses import fields, is_dataclass
import re
import json

from sqlalchemy import text
from sqlalchemy.engine import Connection
from meraki_sync import get_engine

_CAMEL_RE = re.compile(r'(?<!^)(?=[A-Z])')

I = TypeVar("I", bound="MerakiObj")

def camel_to_snake(name: str) -> str:
    return _CAMEL_RE.sub("_", name).lower()

class MerakiObj:
    __schema__: ClassVar[str] = "meraki"
    __mapping_override__: ClassVar[dict[str, str]] = {}

    # Subclasses should override this
    __pk__: ClassVar[tuple[str, ...]] = ("id",)

    # Optional overrides
    __table_name__: ClassVar[str | None] = None
    __no_timestamp__: ClassVar[bool] = False
    __timestamp_fields__: ClassVar[tuple[str, ...]] = (
        "active_from",
        "active_to",
        "last_seen",
    )

    @classmethod
    def from_dashboard(cls: Type[I], data: dict[str, Any]) -> I:
        """
        Convert a Meraki dashboard API response dict (camelCase)
        into a MerakiObj dataclass instance (snake_case)
        """

        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a dataclass")

        field_names = {f.name for f in fields(cls)}

        override = {
                dashboard_key: model_field
                for model_field, dashboard_key in cls.__mapping_override__.items()
                }

        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key in override:
                attr = override[key]
            else:
                attr = camel_to_snake(key)

            if attr in field_names:
                kwargs[attr] = value

        return cls(**kwargs)


    @classmethod
    def from_row(cls: Type[I], row: Any) -> I:
        """
        Convert a SQL row into a MerakiObj dataclass instance.

        Expects query columns to already use snake_case names matching
        the dataclass field names.

        Supports:
        - dict[str, Any]
        - SQLAlchemy Row via row._mapping
        - SQLAlchemy RowMapping
        """
        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a dataclass")

        field_names = {f.name for f in fields(cls)}

        if isinstance(row, dict):
            data = row
        elif hasattr(row, "_mapping"):
            data = dict(row._mapping)
        else:
            data = dict(row)

        kwargs = {
            key: value
            for key, value in data.items()
            if key in field_names
        }

        return cls(**kwargs)

    @classmethod
    def table_name(cls) -> str:
        return cls.__table_name__ or camel_to_snake(cls.__name__)

    @classmethod
    def qualified_table_name(cls) -> str:
        return f"{cls.__schema__}.{cls.table_name()}"

    def to_dict(self) -> dict[str, Any]:
        if not is_dataclass(self):
            raise TypeError(f"{self.__class__.__name__} must be a dataclass")

        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
        }

    @staticmethod
    def _db_value(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    def upsert(
        self,
        conn: Connection | None = None,
        *,
        update_timestamp: bool = True,
    ) -> str:
        """
        Update an existing row by primary key, or insert a new row if no row exists.

        Returns:
            "updated" or "inserted"
        """
        if not conn:
            conn = get_engine().connect()

        cls = self.__class__

        if not is_dataclass(self):
            raise TypeError(f"{cls.__name__} must be a dataclass")

        if not cls.__pk__:
            raise ValueError(f"{cls.__name__} must define __pk__")

        row = self.to_dict()
        timestamp_fields = set(cls.__timestamp_fields__)

        # Insert payload
        insert_data = dict(row)

        if cls.__no_timestamp__:
            for col in timestamp_fields:
                insert_data.pop(col, None)

        # Update payload
        update_data = dict(insert_data)

        if not cls.__no_timestamp__ and not update_timestamp:
            for col in timestamp_fields:
                if col not in cls.__pk__:
                    update_data.pop(col, None)

        # Validate PK fields exist on the object
        missing_pk = [col for col in cls.__pk__ if col not in row]
        if missing_pk:
            raise ValueError(
                f"{cls.__name__} is missing primary key field(s): {missing_pk}"
            )

        # Build WHERE from PK fields
        where_clauses: list[str] = []
        where_params: dict[str, Any] = {}

        for col in cls.__pk__:
            value = row[col]

            if value is None:
                where_clauses.append(f"{col} IS NULL")
            else:
                where_clauses.append(f"{col} = :pk_{col}")
                where_params[f"pk_{col}"] = value

        # Columns eligible for UPDATE
        set_columns = [
            col
            for col in update_data
            if col not in cls.__pk__
        ]

        # If there are columns to update, try UPDATE first
        if set_columns:
            set_clause = ", ".join(f"{col} = :{col}" for col in set_columns)

            update_sql = text(f"""
                UPDATE {cls.qualified_table_name()}
                SET {set_clause}
                WHERE {" AND ".join(where_clauses)}
            """)

            update_params = {
                **{col: cls._db_value(update_data[col]) for col in set_columns},
                **where_params,
            }

            result = conn.execute(update_sql, update_params)

            if result.rowcount and result.rowcount > 0:
                return "updated"

        else:
            # Degenerate case: nothing to update, just check existence
            exists_sql = text(f"""
                SELECT 1
                FROM {cls.qualified_table_name()}
                WHERE {" AND ".join(where_clauses)}
                LIMIT 1
            """)

            exists = conn.execute(exists_sql, where_params).first()
            if exists:
                return "updated"

        # No existing row matched, so INSERT
        if not insert_data:
            raise ValueError(
                f"{cls.__name__} has no columns available for insert"
            )

        insert_columns = list(insert_data.keys())
        insert_col_sql = ", ".join(insert_columns)
        insert_val_sql = ", ".join(f":{col}" for col in insert_columns)
        insert_params = {
                col: cls._db_value(insert_data[col])
                for col in insert_columns
                }

        insert_sql = text(f"""
            INSERT INTO {cls.qualified_table_name()} ({insert_col_sql})
            VALUES ({insert_val_sql})
        """)

        conn.execute(insert_sql, insert_params)
        return "inserted"
