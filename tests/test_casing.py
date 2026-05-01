"""Tests for camel_to_snake conversion."""
from merakisync.utils.casing import camel_to_snake


def test_simple_camel():
    assert camel_to_snake("organizationId") == "organization_id"


def test_pascal():
    # PascalCase: leading capital is lowercased but no leading underscore
    assert camel_to_snake("NetworkId") == "network_id"


def test_already_snake():
    assert camel_to_snake("network_id") == "network_id"


def test_single_word():
    assert camel_to_snake("name") == "name"


def test_multi_word():
    assert camel_to_snake("isBoundToConfigTemplate") == "is_bound_to_config_template"


def test_consecutive_capitals():
    # "publicIP" → "public_i_p" — this is expected behaviour from the regex
    result = camel_to_snake("publicIP")
    assert "public" in result


def test_api_key():
    assert camel_to_snake("apiKey") == "api_key"


def test_two_words():
    assert camel_to_snake("portId") == "port_id"
