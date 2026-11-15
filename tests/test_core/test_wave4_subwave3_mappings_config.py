"""Tests for Wave 4 Sub-Wave 3: Mappings, Config & Parsing (#27–#39)."""
from __future__ import annotations

import pytest
from gunz_utils.dict_utils import (
    DeepDifference,
    compact_dict,
    deep_diff,
    deep_get,
    deep_merge,
    deep_pop,
    deep_set,
    flatten_dict,
    unflatten_dict,
)
from gunz_utils.parsing import (
    parse_bool,
    parse_int_exact,
    parse_key_value_pairs,
    safe_bool,
    safe_float,
    safe_int,
    safe_list,
)
from gunz_utils.typed_config import (
    ConfigValue,
    LayeredConfig,
    convert,
)


# =============================================================================
# #27–#32: dict_utils enhancements
# =============================================================================

def test_deep_diff_reexport():
    d1 = {"a": 1, "b": {"c": 2}}
    d2 = {"a": 1, "b": {"c": 3, "d": 4}}
    diff = deep_diff(d1, d2)
    assert isinstance(diff, list)
    assert len(diff) == 2
    assert all(isinstance(item, DeepDifference) for item in diff)
    paths = {item.path: item for item in diff}
    assert paths["b.c"].kind == "value"
    assert paths["b.c"].left == 2
    assert paths["b.c"].right == 3
    assert paths["b.d"].kind == "missing_left"
    assert paths["b.d"].right == 4


def test_flatten_and_unflatten_dict():
    nested = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "credentials": {"user": "admin"},
        },
        "enabled": True,
    }

    flat = flatten_dict(nested)
    assert flat == {
        "database.host": "localhost",
        "database.port": 5432,
        "database.credentials.user": "admin",
        "enabled": True,
    }

    # Reconstruct
    rebuilt = unflatten_dict(flat)
    assert rebuilt == nested

    # Custom separator and prefix
    flat_custom = flatten_dict(nested, separator="/", prefix="app")
    assert flat_custom["app/database/host"] == "localhost"

    # Cycle detection
    circular: dict = {}
    circular["self"] = circular
    with pytest.raises(ValueError, match="circular reference"):
        flatten_dict(circular)


def test_compact_dict():
    data = {
        "a": 1,
        "b": None,
        "c": {
            "d": None,
            "e": 2,
            "f": {},
        },
        "g": [],
        "h": "",
    }

    # Default: drop_none=True, drop_empty=False
    c1 = compact_dict(data)
    assert c1 == {
        "a": 1,
        "c": {"e": 2, "f": {}},
        "g": [],
        "h": "",
    }

    # drop_empty=True, drop_none=True
    c2 = compact_dict(data, drop_none=True, drop_empty=True)
    assert c2 == {
        "a": 1,
        "c": {"e": 2},
    }


def test_deep_get_sequence_indexing():
    tree = {
        "servers": [
            {"host": "primary.local", "port": 80},
            {"host": "secondary.local", "port": 8080},
        ],
        "tags": ["web", "production"],
    }

    # String dotted paths with integer segments
    assert deep_get(tree, "servers.0.host") == "primary.local"
    assert deep_get(tree, "servers.1.port") == 8080
    assert deep_get(tree, "tags.0") == "web"
    assert deep_get(tree, "tags.1") == "production"

    # Sequence path with ints
    assert deep_get(tree, ["servers", 1, "host"]) == "secondary.local"

    # Out of bounds returns default or raises KeyError
    assert deep_get(tree, "servers.5.host", default="fallback") == "fallback"
    with pytest.raises(KeyError):
        deep_get(tree, "servers.5.host")


def test_deep_merge_cycle_and_depth_limits():
    d1 = {"a": 1}
    d2 = {"b": 2}
    merged = deep_merge(d1, d2)
    assert merged == {"a": 1, "b": 2}

    # Depth limit exceeded
    deep_tree = {"l1": {"l2": {"l3": {"l4": 1}}}}
    with pytest.raises(ValueError, match="maximum mapping merge depth exceeded"):
        deep_merge(deep_tree, {"l1": {"l2": {"l3": {"l4": 2}}}}, max_depth=2)


# =============================================================================
# #33–#35: typed_config.LayeredConfig & ConfigValue
# =============================================================================

def test_layered_config_precedence():
    defaults = {"host": "localhost", "port": 8080, "debug": False}
    file_cfg = {"port": 9000, "db": {"name": "prod"}}
    env_cfg = {"debug": True}
    cli_cfg = {"host": "0.0.0.0"}

    config = LayeredConfig([
        ("defaults", defaults),
        ("file", file_cfg),
        ("env", env_cfg),
        ("cli", cli_cfg),
    ])

    assert config.layers == ["defaults", "file", "env", "cli"]
    assert config["host"] == "0.0.0.0"       # CLI override
    assert config["port"] == 9000            # File override
    assert config["debug"] is True           # Env override
    assert config["db.name"] == "prod"       # File nested
    assert "db.name" in config
    assert "missing" not in config

    # get with default
    assert config.get("missing", "default_val") == "default_val"

    # to_dict
    full = config.to_dict()
    assert full["host"] == "0.0.0.0"
    assert full["port"] == 9000
    assert full["debug"] is True
    assert full["db"] == {"name": "prod"}


def test_layered_config_provenance():
    config = LayeredConfig()
    config.add_layer("base", {"timeout": 30, "server": {"workers": 4}})
    config.add_layer("env", {"server": {"workers": 8}})

    prov_timeout = config.get_provenance("timeout")
    assert prov_timeout is not None
    assert prov_timeout.value == 30
    assert prov_timeout.source == "base"

    prov_workers = config.get_provenance("server.workers")
    assert prov_workers is not None
    assert prov_workers.value == 8
    assert prov_workers.source == "env"

    assert config.get_provenance("nonexistent") is None


def test_config_value_hashable_with_unhashables():
    cv1 = ConfigValue(value=[1, 2, 3], source="cli")
    cv2 = ConfigValue(value={"a": 1}, source="cli")
    # Should not raise TypeError when hashed
    assert isinstance(hash(cv1), int)
    assert isinstance(hash(cv2), int)


# =============================================================================
# #36–#39: parsing helpers & parity
# =============================================================================

def test_parse_key_value_pairs():
    parsed = parse_key_value_pairs("host=localhost, port = 8080 , name='test app', desc=\"my server\"")
    assert parsed == {
        "host": "localhost",
        "port": "8080",
        "name": "test app",
        "desc": "my server",
    }
    assert parse_key_value_pairs("") == {}

    with pytest.raises(ValueError, match="malformed key-value pair"):
        parse_key_value_pairs("invalid_token")


def test_safe_list():
    assert safe_list(None) == []
    assert safe_list("hello") == ["hello"]
    assert safe_list(b"world") == [b"world"]
    assert safe_list([1, 2, 3]) == [1, 2, 3]
    assert safe_list((4, 5)) == [4, 5]
    assert safe_list({6, 7}) in ([6, 7], [7, 6])
    assert safe_list(42) == [42]


def test_parse_int_exact():
    assert parse_int_exact(42) == 42
    assert parse_int_exact("100") == 100
    assert parse_int_exact("-50") == -50
    assert parse_int_exact("+12") == 12
    assert parse_int_exact(b"999") == 999

    with pytest.raises(TypeError, match="cannot parse exact int from bool"):
        parse_int_exact(True)
    with pytest.raises(TypeError, match="cannot parse exact int from bool"):
        parse_int_exact(False)
    with pytest.raises(TypeError, match="cannot parse exact int from float"):
        parse_int_exact(3.14)
    with pytest.raises(ValueError, match="invalid exact integer"):
        parse_int_exact("3.14")
    with pytest.raises(ValueError, match="invalid exact integer"):
        parse_int_exact("abc")
    with pytest.raises(ValueError, match="cannot parse exact int from empty string"):
        parse_int_exact("  ")
