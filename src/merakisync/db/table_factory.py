from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, get_args, get_origin, Optional, Union

import sqlalchemy as sa
from meraki_sync.db.models import Base
from meraki_sync.meraki.models.base import MerakiObj


def _is_optional(tp: Any) -> bool:
    return get_origin(tp) is Union and type(None) in get_args(tp)


def _unwrap_optional(tp: Any) -> Any:
    return next(t for t in get_args(tp) if t is not type(None))


def _sa_type(tp: Any) -> sa.types.TypeEngine:
    # unwrap Optional[T]
    if _is_optional(tp):
        tp = _unwrap_optional(tp)

    # map python types -> SQLAlchemy types (extend as needed)
    if tp is str:
        return sa.String()
    if tp is int:
        return sa.Integer()
    if tp is bool:
        return sa.Boolean()
    # datetime example
    import datetime as dt
    if tp is dt.datetime:
        return sa.DateTime(timezone=True)

    # fallback (you can make this stricter)
    return sa.String()


def build_table_from_model(model_cls: type[MerakiObj]) -> sa.Table:
    if not is_dataclass(model_cls):
        raise TypeError(f"{model_cls.__name__} must be a dataclass")

    schema = getattr(model_cls, "__schema__", "meraki")
    table_name = model_cls.__table_name__
    pk_cols = set(model_cls.__pk__)
    mapping = dict(getattr(model_cls, "__mapping_override__", {}))

    cols: list[sa.Column] = []

    for f in fields(model_cls):
        col_name = mapping.get(f.name, f.name)
        nullable = _is_optional(f.type) or f.default is not f.default_factory  # simple-ish

        col = sa.Column(
            col_name,
            _sa_type(f.type),
            primary_key=(col_name in pk_cols),
            nullable=(False if col_name in pk_cols else nullable),
        )
        cols.append(col)

    return sa.Table(
        table_name,
        Base.metadata,
        *cols,
        schema=schema,
    )
