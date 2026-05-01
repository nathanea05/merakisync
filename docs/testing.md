# Testing

This document explains how tests are structured in merakisync, how to run them, and how to write new tests when adding models or changing behaviour.

---

## Running tests

```bash
# Run the full suite
python3 -m pytest tests/ -v

# Run a single file
python3 -m pytest tests/test_models_base.py -v

# Run a single test
python3 -m pytest tests/test_config.py::TestGetConfigEnvOverlay::test_env_overrides_file -v

# Run with coverage
python3 -m pytest tests/ --cov=merakisync --cov-report=term-missing
```

If pytest is not installed:

```bash
pip install -e ".[dev]"
```

---

## Test structure

```
tests/
├── __init__.py
├── test_casing.py        camel_to_snake conversion
├── test_filter_array.py  include/exclude set filtering
├── test_models_base.py   MerakiObj base class (from_dashboard, from_row, _data_equal)
└── test_config.py        Configuration loading, env var overlay, write_config
```

Tests are grouped by the module they test, not by test type. Each file contains one or more test classes, each class grouping related tests.

---

## What to test and what to skip

### Test these

- `from_dashboard()` — correct field mapping, `__mapping_override__` applied, unknown keys ignored, nested object flattening (for models that override `from_dashboard`).
- `from_row()` — round-trip from a plain dict or mock SQLAlchemy row.
- `_data_fields()` — PK columns and versioning fields excluded.
- `get()` validation logic — e.g., `ValueError` raised when `ts` is used with `source="meraki"`.
- `__mapping_override__` entries — especially any non-trivial remapping (Python reserved words, irregular camelCase).
- `config.py` — env var overlay, file loading, `write_config` permissions.
- `utils/` — `camel_to_snake`, `filter_array`, `confirm`, `prompt`.

### Do not test these without a real database

- `upsert()` / `upsert_many()` — these require a live PostgreSQL connection. They are integration tests, not unit tests. Test them manually against a dev database, not in the automated suite.
- `sync()` — calls the Meraki API and writes to the database. Integration test only.
- `get(source="database")` — requires a live database.
- `get(source="meraki")` — requires a live API key.

The automated test suite is intentionally limited to pure unit tests that run without any network or database access. This makes them fast and runnable anywhere.

---

## Writing tests for a new model

When you add a new model (see `adding-a-model.md`), create `tests/test_<model_name>.py`.

### Minimal test file structure

```python
"""Tests for the Vlan model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

import pytest

from merakisync.models.vlan import Vlan


class TestVlanFromDashboard:
    """Tests for Vlan.from_dashboard()."""

    def test_basic_field_mapping(self):
        raw = {
            "id": 100,
            "networkId": "N_123",
            "name": "Management",
            "applianceIp": "192.168.1.1",
            "subnet": "192.168.1.0/24",
        }
        vlan = Vlan.from_dashboard(raw)
        assert vlan.vlan_id == 100
        assert vlan.network_id == "N_123"
        assert vlan.name == "Management"
        assert vlan.appliance_ip == "192.168.1.1"

    def test_mapping_override_renames_id(self):
        # "id" in the API response must map to vlan_id, not id
        raw = {"id": 100, "networkId": "N_123", "name": "Test"}
        vlan = Vlan.from_dashboard(raw)
        assert vlan.vlan_id == 100

    def test_unknown_keys_ignored(self):
        raw = {"id": 100, "networkId": "N_123", "name": "Test", "futureField": "ignored"}
        vlan = Vlan.from_dashboard(raw)
        assert vlan.vlan_id == 100

    def test_optional_fields_default_to_none(self):
        raw = {"id": 100, "networkId": "N_123", "name": "Test"}
        vlan = Vlan.from_dashboard(raw)
        assert vlan.appliance_ip is None
        assert vlan.dns_nameservers is None

    def test_versioning_fields_not_populated_by_dashboard(self):
        raw = {"id": 100, "networkId": "N_123", "name": "Test"}
        vlan = Vlan.from_dashboard(raw)
        assert vlan.active_from is None
        assert vlan.active_to is None
        assert vlan.last_seen is None


class TestVlanFromRow:
    """Tests for Vlan.from_row() — simulates reading from the database."""

    def test_from_plain_dict(self):
        now = datetime.now(tz=timezone.utc)
        row = {
            "network_id": "N_123",
            "vlan_id": 100,
            "name": "Management",
            "appliance_ip": "192.168.1.1",
            "active_from": now,
            "active_to": None,
            "last_seen": now,
        }
        vlan = Vlan.from_row(row)
        assert vlan.vlan_id == 100
        assert vlan.name == "Management"
        assert vlan.active_from == now

    def test_extra_db_columns_ignored(self):
        row = {"network_id": "N_123", "vlan_id": 100, "name": "Test", "_internal": "x"}
        vlan = Vlan.from_row(row)
        assert vlan.vlan_id == 100


class TestVlanDataFields:
    """Tests for Vlan._data_fields() — used by SCD2 change detection."""

    def test_pk_excluded(self):
        vlan = Vlan(network_id="N_123", vlan_id=100, name="Test")
        data = vlan._data_fields()
        assert "network_id" not in data
        assert "vlan_id" not in data

    def test_versioning_fields_excluded(self):
        now = datetime.now(tz=timezone.utc)
        vlan = Vlan(network_id="N_123", vlan_id=100, name="Test", active_from=now)
        data = vlan._data_fields()
        assert "active_from" not in data
        assert "active_to" not in data
        assert "last_seen" not in data

    def test_business_fields_present(self):
        vlan = Vlan(network_id="N_123", vlan_id=100, name="Test", appliance_ip="1.2.3.4")
        data = vlan._data_fields()
        assert data["name"] == "Test"
        assert data["appliance_ip"] == "1.2.3.4"


class TestVlanGetValidation:
    """Tests for get() argument validation."""

    def test_ts_with_meraki_source_raises(self):
        from datetime import timezone
        with pytest.raises(ValueError, match="Timestamp lookups"):
            Vlan.get(
                "N_123",
                source="meraki",
                ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Vlan.get("N_123", source="invalid")  # type: ignore[arg-type]
```

### Testing custom from_dashboard logic

If your model overrides `from_dashboard` to flatten nested objects, test that specifically:

```python
def test_nested_object_flattened(self):
    raw = {
        "id": "alert-123",
        "network": {"id": "N_456", "name": "Branch Office"},
        "type": "connectivity",
    }
    alert = Alert.from_dashboard(raw)
    assert alert.network_id == "N_456"
    assert alert.network_name == "Branch Office"
    # The raw "network" key should not appear as a field
    assert not hasattr(alert, "network")
```

---

## Testing utility functions

Utility functions in `utils/` should each have a corresponding test file that covers both normal cases and edge cases.

Pattern to follow (see `tests/test_filter_array.py`):

```python
"""Tests for utils/my_utility.py"""
from merakisync.utils.my_utility import my_function

def test_normal_case():
    assert my_function(input) == expected

def test_edge_case_empty():
    assert my_function([]) == expected_for_empty

def test_edge_case_none():
    ...
```

---

## Mocking strategy

For tests that need to simulate database rows or Meraki API responses, use plain dicts rather than mocking the full SQLAlchemy or Meraki SDK. The `from_dashboard()` and `from_row()` methods accept plain dicts.

```python
# Simulate a database row — no SQLAlchemy needed
row = {"serial": "Q2AB-1234", "model": "MS225-48", "active_to": None}
device = Device.from_row(row)

# Simulate an API response — no Meraki SDK needed
raw = {"serial": "Q2AB-1234", "model": "MS225-48", "networkId": "N_123"}
device = Device.from_dashboard(raw)
```

Only mock `get_dashboard()` or `get_engine()` if you are testing code that calls them. Use `unittest.mock.patch`:

```python
from unittest.mock import MagicMock, patch

def test_sync_calls_upsert_many(self):
    mock_dashboard = MagicMock()
    mock_dashboard.organizations.getOrganizations.return_value = [
        {"id": "org-1", "name": "Test Org", "url": "https://..."},
    ]

    with patch("merakisync.dashboard.get_dashboard", return_value=mock_dashboard), \
         patch.object(Organization, "upsert_many", return_value={"inserted": 1}) as mock_upsert:
        result = Organization.sync()

    mock_upsert.assert_called_once()
    assert len(result) == 1
```

---

## CI / automation

Tests run automatically on every push if a CI pipeline is configured. To add one, create a workflow file that runs:

```bash
pip install -e ".[dev]"
python3 -m pytest tests/ -v
```

No database or Meraki credentials are needed to run the unit test suite.
