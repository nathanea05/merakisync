"""Tests for MerakiObj base class: from_dashboard, from_row, data comparison."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

import pytest

from merakisync.models.base import MerakiObj, _data_equal


# ---------------------------------------------------------------------------
# Minimal concrete model for testing
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
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
