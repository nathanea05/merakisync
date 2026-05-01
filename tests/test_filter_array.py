"""Tests for filter_array utility."""
from merakisync.utils.filter_array import filter_array


def test_no_filters():
    assert filter_array({"a", "b"}, [], []) is True


def test_include_all_present():
    assert filter_array({"switch", "wireless"}, ["switch"], []) is True


def test_include_missing():
    assert filter_array({"wireless"}, ["switch"], []) is False


def test_exclude_match():
    assert filter_array({"switch", "appliance"}, [], ["appliance"]) is False


def test_exclude_no_match():
    assert filter_array({"switch"}, [], ["appliance"]) is True


def test_include_and_exclude_pass():
    assert filter_array({"switch", "wireless"}, ["switch"], ["appliance"]) is True


def test_include_and_exclude_fail_include():
    assert filter_array({"wireless"}, ["switch"], ["appliance"]) is False


def test_include_and_exclude_fail_exclude():
    assert filter_array({"switch", "appliance"}, ["switch"], ["appliance"]) is False


def test_empty_values():
    assert filter_array(set(), ["switch"], []) is False


def test_empty_values_no_filters():
    assert filter_array(set(), [], []) is True
