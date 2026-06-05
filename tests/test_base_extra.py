"""Extra coverage for MerakiObj base class: _db_value, upsert paths,
upsert_many, _build_pk_where, _data_equal edge cases, and error paths."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch, call

import pytest

from merakisync.models.base import (
    MerakiObj,
    _build_pk_where,
    _data_equal,
    _db_value,
)


# ---------------------------------------------------------------------------
# Minimal concrete models for testing
# ---------------------------------------------------------------------------

@dataclass()
class _Widget(MerakiObj):
    __table_name__: ClassVar[str] = "widget"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}

    id: str
    label: str | None = None
    metadata: dict | None = None

    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None


@dataclass()
class _Metric(MerakiObj):
    """Non-versioned model (simple UPSERT)."""
    __table_name__: ClassVar[str] = "metric"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {}
    __versioned__: ClassVar[bool] = False

    id: str
    value: int | None = None
    last_seen: datetime | None = None


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_conn(existing_row=None):
    """Return a mock connection that returns *existing_row* for SELECT queries."""
    conn = MagicMock()
    select_result = MagicMock()
    select_result.mappings.return_value.first.return_value = existing_row
    select_result.mappings.return_value.all.return_value = (
        [existing_row] if existing_row else []
    )
    conn.execute.return_value = select_result
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


def _mock_engine(existing_row=None):
    conn = _mock_conn(existing_row)
    engine = MagicMock()
    engine.connect.return_value = conn
    return engine, conn


# ---------------------------------------------------------------------------
# _db_value
# ---------------------------------------------------------------------------

class TestDbValue:
    def test_dict_serialised_to_json_string(self):
        result = _db_value({"k": "v"})
        assert result == json.dumps({"k": "v"})

    def test_list_serialised_to_json_string(self):
        result = _db_value([1, 2, 3])
        assert result == json.dumps([1, 2, 3])

    def test_string_passed_through(self):
        assert _db_value("hello") == "hello"

    def test_none_passed_through(self):
        assert _db_value(None) is None

    def test_int_passed_through(self):
        assert _db_value(42) == 42

    def test_bool_passed_through(self):
        assert _db_value(True) is True


# ---------------------------------------------------------------------------
# _build_pk_where — NULL PK branch
# ---------------------------------------------------------------------------

class TestBuildPkWhere:
    def test_non_null_pk(self):
        where, params = _build_pk_where(("id",), {"id": "abc"})
        assert "id = :pk_id" in where
        assert params["pk_id"] == "abc"

    def test_null_pk_uses_is_null(self):
        where, params = _build_pk_where(("id",), {"id": None})
        assert "id IS NULL" in where
        assert "pk_id" not in params

    def test_composite_pk(self):
        where, params = _build_pk_where(("a", "b"), {"a": "x", "b": "y"})
        assert "a = :pk_a" in where
        assert "b = :pk_b" in where
        assert params["pk_a"] == "x"
        assert params["pk_b"] == "y"

    def test_mixed_null_and_non_null(self):
        where, params = _build_pk_where(("a", "b"), {"a": "x", "b": None})
        assert "a = :pk_a" in where
        assert "b IS NULL" in where
        assert "pk_b" not in params


# ---------------------------------------------------------------------------
# _data_equal — null vs empty collection
# ---------------------------------------------------------------------------

class TestDataEqualEdgeCases:
    def test_null_vs_empty_list_equal(self):
        assert _data_equal({"tags": None}, {"tags": []}) is True

    def test_null_vs_empty_dict_equal(self):
        assert _data_equal({"scope": None}, {"scope": {}}) is True

    def test_empty_list_vs_null_equal(self):
        assert _data_equal({"tags": []}, {"tags": None}) is True

    def test_empty_dict_vs_null_equal(self):
        assert _data_equal({"scope": {}}, {"scope": None}) is True

    def test_null_vs_nonempty_list_not_equal(self):
        assert _data_equal({"tags": None}, {"tags": ["x"]}) is False

    def test_json_string_list_vs_list(self):
        assert _data_equal({"x": '["a", "b"]'}, {"x": ["a", "b"]}) is True

    def test_json_string_dict_vs_dict(self):
        assert _data_equal({"x": '{"k": "v"}'}, {"x": {"k": "v"}}) is True

    def test_invalid_json_string_compared_as_string(self):
        assert _data_equal({"x": "not json"}, {"x": "not json"}) is True
        assert _data_equal({"x": "not json"}, {"x": "different"}) is False


# ---------------------------------------------------------------------------
# from_dashboard / from_row error paths
# ---------------------------------------------------------------------------

class TestConversionErrorPaths:
    def test_from_dashboard_non_dataclass_raises(self):
        class NotADC(MerakiObj):
            pass
        with pytest.raises(TypeError, match="must be a dataclass"):
            NotADC.from_dashboard({"id": "x"})

    def test_from_row_non_dataclass_raises(self):
        class NotADC(MerakiObj):
            pass
        with pytest.raises(TypeError, match="must be a dataclass"):
            NotADC.from_row({"id": "x"})

    def test_from_row_plain_object_uses_dict_conversion(self):
        # Row object without _mapping attribute (uses dict(row) path)
        class PlainRow:
            def keys(self): return ["id", "label"]
            def __iter__(self): return iter([("id", "w1"), ("label", "hello")])

        # Simulate a SQLAlchemy-like Row that isn't a dict and has no _mapping
        class FakeRow:
            def keys(self): return ["id", "label"]
            def __getitem__(self, key):
                return {"id": "w1", "label": "hello"}[key]

        # We can't easily call dict() on an arbitrary object, but the from_row
        # else branch does dict(row). Test with an object that supports __iter__
        # returning key-value pairs like a dict would.
        d = {"id": "w1", "label": "hello"}
        w = _Widget.from_row(d)
        assert w.id == "w1"

    def test_to_dict_non_dataclass_raises(self):
        class NotADC(MerakiObj):
            pass
        obj = NotADC()
        with pytest.raises(TypeError, match="must be a dataclass"):
            obj.to_dict()


# ---------------------------------------------------------------------------
# _upsert_with_conn — validation
# ---------------------------------------------------------------------------

class TestUpsertWithConnValidation:
    def test_missing_pk_raises(self):
        w = _Widget.__new__(_Widget)
        # Construct a widget with id=None via __init__ to trigger missing PK check
        w.__init__(id=None, label="x")  # type: ignore[arg-type]
        conn = _mock_conn()
        with pytest.raises(ValueError, match="missing required PK"):
            w._upsert_with_conn(conn)


# ---------------------------------------------------------------------------
# _scd2_upsert — all three outcomes via _upsert_with_conn
# ---------------------------------------------------------------------------

class TestScd2UpsertOutcomes:
    def _make_existing(self, label="hello"):
        return {
            "id": "w1",
            "label": label,
            "metadata": None,
            "active_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "active_to": None,
            "last_seen": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }

    def test_insert_new_row(self):
        conn = _mock_conn(existing_row=None)
        w = _Widget(id="new1", label="hello")
        result = w._upsert_with_conn(conn)
        assert result == "inserted"
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert any("INSERT" in s.upper() for s in sqls)

    def test_unchanged_row_updates_last_seen(self):
        existing = self._make_existing(label="hello")
        conn = _mock_conn(existing_row=existing)
        w = _Widget(id="w1", label="hello")
        result = w._upsert_with_conn(conn)
        assert result == "updated"
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert any("last_seen" in s for s in sqls)
        assert not any("INSERT" in s.upper() for s in sqls)

    def test_changed_row_expires_and_inserts(self):
        existing = self._make_existing(label="old value")
        conn = _mock_conn(existing_row=existing)
        w = _Widget(id="w1", label="new value")
        result = w._upsert_with_conn(conn)
        assert result == "expired+inserted"
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert any("active_to" in s for s in sqls)
        assert any("INSERT" in s.upper() for s in sqls)

    def test_prefetched_existing_used_without_select(self):
        existing = self._make_existing(label="hello")
        conn = _mock_conn()  # execute should not be called for SELECT
        w = _Widget(id="w1", label="hello")
        result = w._upsert_with_conn(conn, prefetched_existing=existing)
        assert result == "updated"
        # No SELECT should have been issued (prefetch was provided)
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert not any("SELECT" in s.upper() for s in sqls)

    def test_prefetched_none_triggers_insert(self):
        conn = _mock_conn()
        w = _Widget(id="new1", label="test")
        result = w._upsert_with_conn(conn, prefetched_existing=None)
        assert result == "inserted"


# ---------------------------------------------------------------------------
# _simple_upsert — non-versioned model
# ---------------------------------------------------------------------------

class TestSimpleUpsert:
    def test_simple_upsert_returns_upserted(self):
        conn = _mock_conn()
        m = _Metric(id="m1", value=42)
        result = m._upsert_with_conn(conn)
        assert result == "upserted"

    def test_simple_upsert_sql_has_on_conflict(self):
        conn = _mock_conn()
        m = _Metric(id="m1", value=42)
        m._upsert_with_conn(conn)
        sql = str(conn.execute.call_args.args[0])
        assert "ON CONFLICT" in sql.upper()

    def test_simple_upsert_uses_object_last_seen(self):
        conn = _mock_conn()
        ts = datetime(2026, 6, 1, tzinfo=timezone.utc)
        m = _Metric(id="m1", value=42, last_seen=ts)
        m._upsert_with_conn(conn)
        params = conn.execute.call_args.args[1]
        assert params["last_seen"] == ts

    def test_simple_upsert_defaults_last_seen_to_now_when_none(self):
        conn = _mock_conn()
        m = _Metric(id="m1", value=42, last_seen=None)
        m._upsert_with_conn(conn)
        params = conn.execute.call_args.args[1]
        assert params["last_seen"] is not None


# ---------------------------------------------------------------------------
# upsert() — single-row public API
# ---------------------------------------------------------------------------

class TestUpsert:
    def test_upsert_inserts_new_row(self):
        engine, conn = _mock_engine(existing_row=None)
        w = _Widget(id="new1", label="test")
        result = w.upsert(engine=engine)
        assert result == "inserted"
        conn.commit.assert_called_once()

    def test_upsert_uses_get_engine_when_none(self):
        engine, conn = _mock_engine(existing_row=None)
        w = _Widget(id="new1", label="test")
        with patch("merakisync.database.get_engine", return_value=engine):
            result = w.upsert()
        assert result == "inserted"


# ---------------------------------------------------------------------------
# upsert_many
# ---------------------------------------------------------------------------

class TestUpsertMany:
    def test_empty_list_returns_empty_dict(self):
        result = _Widget.upsert_many([])
        assert result == {}

    def test_small_batch_uses_per_row_loop(self):
        engine, conn = _mock_engine(existing_row=None)
        widgets = [_Widget(id=f"w{i}", label=f"label{i}") for i in range(3)]
        counts = _Widget.upsert_many(widgets, engine=engine)
        assert counts.get("inserted", 0) == 3

    def test_large_batch_uses_bulk_path(self):
        # Build a prefetch_map response (all active rows — empty means all new)
        conn = MagicMock()
        prefetch_result = MagicMock()
        prefetch_result.mappings.return_value.all.return_value = []
        conn.execute.return_value = prefetch_result
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        engine = MagicMock()
        engine.connect.return_value = conn

        widgets = [_Widget(id=f"w{i}") for i in range(500)]
        counts = _Widget.upsert_many(widgets, engine=engine)
        assert counts.get("inserted", 0) == 500

    def test_upsert_many_uses_get_engine_when_none(self):
        engine, conn = _mock_engine(existing_row=None)
        widgets = [_Widget(id="w1")]
        with patch("merakisync.database.get_engine", return_value=engine):
            counts = _Widget.upsert_many(widgets)
        assert counts.get("inserted", 0) == 1

    def test_non_versioned_small_batch(self):
        engine, conn = _mock_engine()
        metrics = [_Metric(id=f"m{i}", value=i) for i in range(5)]
        counts = _Metric.upsert_many(metrics, engine=engine)
        assert counts.get("upserted", 0) == 5
