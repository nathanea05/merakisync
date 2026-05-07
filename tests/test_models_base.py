"""Tests for MerakiObj base class: from_dashboard, from_row, data comparison,
to_meraki_dict, and _changed_fields tracking."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

import pytest

from merakisync.models.base import MerakiObj, _data_equal


# ---------------------------------------------------------------------------
# Minimal concrete model for testing
# ---------------------------------------------------------------------------

@dataclass()
class _Widget(MerakiObj):
    __table_name__: ClassVar[str] = "widget"
    __pk__: ClassVar[tuple[str, ...]] = ("id",)
    __mapping_override__: ClassVar[dict[str, str]] = {
        "widget_type": "type",
        "is_active": "isActive",
    }

    id: str
    widget_type: str | None = None
    is_active: bool | None = None
    label: str | None = None
    metadata: dict | None = None

    active_from: datetime | None = None
    active_to: datetime | None = None
    last_seen: datetime | None = None


# ---------------------------------------------------------------------------
# from_dashboard
# ---------------------------------------------------------------------------

class TestFromDashboard:
    def test_simple_camel_conversion(self):
        w = _Widget.from_dashboard({"id": "w1", "label": "hello"})
        assert w.id == "w1"
        assert w.label == "hello"

    def test_mapping_override_applied(self):
        w = _Widget.from_dashboard({"id": "w1", "type": "button", "isActive": True})
        assert w.widget_type == "button"
        assert w.is_active is True

    def test_unknown_keys_ignored(self):
        w = _Widget.from_dashboard({"id": "w1", "unknownField": "ignored"})
        assert w.id == "w1"

    def test_missing_optional_fields_are_none(self):
        w = _Widget.from_dashboard({"id": "w1"})
        assert w.label is None
        assert w.widget_type is None

    def test_versioning_fields_not_set_from_dashboard(self):
        w = _Widget.from_dashboard({"id": "w1", "active_from": "2026-01-01"})
        # active_from is a snake_case field that matches, so it WILL be set
        # (API won't return it, but the mapping doesn't block it)
        # More important: active_to and last_seen default to None
        assert w.active_to is None
        assert w.last_seen is None

    def test_dict_field_passed_through(self):
        w = _Widget.from_dashboard({"id": "w1", "metadata": {"k": "v"}})
        assert w.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# from_row
# ---------------------------------------------------------------------------

class TestFromRow:
    def test_from_plain_dict(self):
        w = _Widget.from_row({"id": "w1", "label": "hello", "active_to": None})
        assert w.id == "w1"
        assert w.label == "hello"
        assert w.active_to is None

    def test_extra_columns_ignored(self):
        w = _Widget.from_row({"id": "w1", "pg_internal_col": "x"})
        assert w.id == "w1"

    def test_mapping_object_with__mapping(self):
        class FakeRow:
            _mapping = {"id": "w2", "label": "foo"}
        w = _Widget.from_row(FakeRow())
        assert w.id == "w2"
        assert w.label == "foo"


# ---------------------------------------------------------------------------
# _data_equal
# ---------------------------------------------------------------------------

class TestDataEqual:
    def test_equal_dicts(self):
        assert _data_equal({"a": 1, "b": "x"}, {"a": 1, "b": "x"}) is True

    def test_unequal_value(self):
        assert _data_equal({"a": 1}, {"a": 2}) is False

    def test_different_keys(self):
        assert _data_equal({"a": 1}, {"b": 1}) is False

    def test_json_string_vs_dict(self):
        # DB returns JSON as string; Python object may be dict
        assert _data_equal({"x": '{"k": "v"}'}, {"x": {"k": "v"}}) is True

    def test_json_string_vs_list(self):
        assert _data_equal({"x": '[1, 2]'}, {"x": [1, 2]}) is True

    def test_none_values_equal(self):
        assert _data_equal({"a": None}, {"a": None}) is True

    def test_none_vs_value(self):
        assert _data_equal({"a": None}, {"a": "something"}) is False


# ---------------------------------------------------------------------------
# _data_fields
# ---------------------------------------------------------------------------

class TestDataFields:
    def test_excludes_pk(self):
        w = _Widget(id="w1", label="hello")
        data = w._data_fields()
        assert "id" not in data

    def test_excludes_versioning(self):
        now = datetime.now(tz=timezone.utc)
        w = _Widget(id="w1", label="hello", active_from=now, last_seen=now)
        data = w._data_fields()
        assert "active_from" not in data
        assert "last_seen" not in data
        assert "active_to" not in data

    def test_includes_business_fields(self):
        w = _Widget(id="w1", label="hello", widget_type="button")
        data = w._data_fields()
        assert data["label"] == "hello"
        assert data["widget_type"] == "button"


# ---------------------------------------------------------------------------
# to_meraki_dict
# ---------------------------------------------------------------------------

class TestToMerakiDict:
    def test_snake_fields_become_camel(self):
        w = _Widget(id="w1", label="hello", is_active=True)
        d = w.to_meraki_dict()
        assert "label" in d
        assert "isActive" in d

    def test_mapping_override_applied(self):
        w = _Widget(id="w1", widget_type="button")
        d = w.to_meraki_dict()
        # widget_type -> "type" per __mapping_override__
        assert "type" in d
        assert "widgetType" not in d

    def test_versioning_fields_excluded(self):
        now = datetime.now(tz=timezone.utc)
        w = _Widget(id="w1", active_from=now, active_to=None, last_seen=now)
        d = w.to_meraki_dict()
        assert "active_from" not in d
        assert "activeFrom" not in d
        assert "activeTo" not in d
        assert "lastSeen" not in d

    def test_fields_filter_snake_case_input(self):
        w = _Widget(id="w1", label="hello", widget_type="button", is_active=True)
        d = w.to_meraki_dict(fields=["id", "label"])
        assert set(d.keys()) == {"id", "label"}

    def test_fields_filter_returns_camel_keys(self):
        w = _Widget(id="w1", is_active=True, widget_type="button")
        d = w.to_meraki_dict(fields=["is_active", "widget_type"])
        assert "isActive" in d
        assert "type" in d  # mapped via __mapping_override__
        assert "is_active" not in d
        assert "widget_type" not in d

    def test_none_values_included(self):
        w = _Widget(id="w1")
        d = w.to_meraki_dict()
        assert "label" in d
        assert d["label"] is None

    def test_dict_field_included(self):
        w = _Widget(id="w1", metadata={"k": "v"})
        d = w.to_meraki_dict()
        assert d["metadata"] == {"k": "v"}


# ---------------------------------------------------------------------------
# _changed_fields
# ---------------------------------------------------------------------------

class TestChangedFields:
    def test_empty_after_construction(self):
        w = _Widget(id="w1", label="hello")
        assert w._changed_fields == set()

    def test_tracks_assignment(self):
        w = _Widget(id="w1")
        w.label = "new value"
        assert "label" in w._changed_fields

    def test_tracks_multiple_assignments(self):
        w = _Widget(id="w1")
        w.label = "a"
        w.is_active = True
        assert "label" in w._changed_fields
        assert "is_active" in w._changed_fields

    def test_reassignment_keeps_field_in_set(self):
        w = _Widget(id="w1", label="original")
        w.label = "first change"
        w.label = "second change"
        assert "label" in w._changed_fields
        assert w.label == "second change"

    def test_changed_fields_not_in_to_dict(self):
        w = _Widget(id="w1")
        w.label = "x"
        assert "_changed_fields" not in w.to_dict()

    def test_changed_fields_not_in_data_fields(self):
        w = _Widget(id="w1")
        w.label = "x"
        assert "_changed_fields" not in w._data_fields()

    def test_from_dashboard_starts_clean(self):
        w = _Widget.from_dashboard({"id": "w1", "label": "hello"})
        assert w._changed_fields == set()

    def test_from_row_starts_clean(self):
        w = _Widget.from_row({"id": "w1", "label": "hello"})
        assert w._changed_fields == set()

    def test_pk_fields_are_immutable(self):
        w = _Widget(id="w1")
        with pytest.raises(AttributeError, match="primary key"):
            w.id = "w2"

    def test_non_pk_fields_are_mutable(self):
        w = _Widget(id="w1", label="original")
        w.label = "updated"
        assert w.label == "updated"


# ---------------------------------------------------------------------------
# _bulk_scd2_upsert  (categorisation logic — no real DB required)
# ---------------------------------------------------------------------------

class TestBulkScd2Upsert:
    """Verify the Python categorisation logic without a real database connection.

    We use a mock connection that captures every (statement, params) call so
    we can assert exactly which executemany batches were issued.
    """

    class _MockConn:
        def __init__(self):
            self.calls: list[tuple] = []

        def execute(self, stmt, params=None):
            self.calls.append((str(stmt), params))

    def _make_prefetch(self, widget: _Widget) -> dict:
        """Return a prefetch_map entry for a widget as it would come from the DB."""
        from merakisync.models.base import _VERSIONING_FIELDS
        return {(widget.id,): {
            "id": widget.id,
            "widget_type": widget.widget_type,
            "is_active": widget.is_active,
            "label": widget.label,
            "metadata": widget.metadata,
        }}

    def test_new_row_issues_insert(self):
        conn = self._MockConn()
        w = _Widget(id="new1", label="hello")
        counts = _Widget._bulk_scd2_upsert(conn, [w], prefetch_map={})
        assert counts["inserted"] == 1
        assert counts["updated"] == 0
        assert counts["expired+inserted"] == 0
        # Should be exactly one execute call: the INSERT
        assert any("INSERT" in call[0].upper() for call in conn.calls)

    def test_unchanged_row_issues_last_seen_update(self):
        conn = self._MockConn()
        w = _Widget(id="w1", label="hello")
        prefetch = self._make_prefetch(w)
        counts = _Widget._bulk_scd2_upsert(conn, [w], prefetch_map=prefetch)
        assert counts["updated"] == 1
        assert counts["inserted"] == 0
        assert counts["expired+inserted"] == 0
        update_calls = [c for c in conn.calls if "UPDATE" in c[0].upper()]
        assert len(update_calls) == 1
        assert "last_seen" in update_calls[0][0]

    def test_changed_row_issues_expire_and_insert(self):
        conn = self._MockConn()
        old = _Widget(id="w1", label="old")
        prefetch = self._make_prefetch(old)
        new = _Widget(id="w1", label="new")
        counts = _Widget._bulk_scd2_upsert(conn, [new], prefetch_map=prefetch)
        assert counts["expired+inserted"] == 1
        assert counts["inserted"] == 0
        assert counts["updated"] == 0
        update_calls = [c for c in conn.calls if "UPDATE" in c[0].upper()]
        assert len(update_calls) == 1
        assert "active_to" in update_calls[0][0]
        insert_calls = [c for c in conn.calls if "INSERT" in c[0].upper()]
        assert len(insert_calls) == 1

    def test_mixed_batch_issues_correct_counts(self):
        conn = self._MockConn()
        existing_unchanged = _Widget(id="same", label="same")
        existing_changed = _Widget(id="changed", label="old")
        new_widget = _Widget(id="brand_new", label="new")

        prefetch = {}
        prefetch.update(self._make_prefetch(existing_unchanged))
        prefetch.update(self._make_prefetch(existing_changed))

        rows = [
            _Widget(id="same", label="same"),        # unchanged
            _Widget(id="changed", label="updated"),  # changed
            new_widget,                               # new
        ]
        counts = _Widget._bulk_scd2_upsert(conn, rows, prefetch_map=prefetch)
        assert counts["inserted"] == 1
        assert counts["updated"] == 1
        assert counts["expired+inserted"] == 1
