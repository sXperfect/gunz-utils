"""Tests for Wave 6 Sub-Wave 3: Hierarchical Data Diffs, Patching & Inversion."""

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.diff import (
    DiffOp,
    deep_diff,
    diff_dicts,
    filter_diffs,
    format_diff_summary,
    has_changes,
    invert_diff,
    patch_dict,
    resolve_path,
    set_path,
)


def test_deep_diff_dicts():
    a = {"name": "Alice", "meta": {"role": "dev", "age": 30}, "tags": ["a", "b"]}
    b = {
    "name": "Alice",
    "meta": {
        "role": "admin",
        "age": 30},
        "tags": [
            "a",
            "c"],
             "city": "NYC"}

    diffs = diff_dicts(a, b)
    assert has_changes(diffs)

    #? Check additions
    adds = filter_diffs(diffs, {DiffOp.ADDED})
    assert len(adds) == 1
    assert adds[0].path == ("city",)
    assert adds[0].new_value == "NYC"

    #? Check modifications
    mods = filter_diffs(diffs, {DiffOp.MODIFIED})
    mod_paths = [m.path for m in mods]
    assert ("meta", "role") in mod_paths
    assert ("tags", 1) in mod_paths


def test_patch_and_invert():
    orig = {"a": 1, "nested": {"x": 10, "y": 20}}
    target = {"a": 2, "nested": {"x": 10, "z": 30}}

    diffs = deep_diff(orig, target)
    patched = patch_dict(orig, diffs)
    assert patched == target

    #? Invert diffs and patch back
    inv = invert_diff(diffs)
    reverted = patch_dict(patched, inv)
    assert reverted == orig


def test_format_diff_summary():
    a = {"foo": 1}
    b = {"foo": 2, "bar": "added"}
    diffs = deep_diff(a, b)
    summary = format_diff_summary(diffs)
    assert "+ bar: 'added'" in summary
    assert "~ foo: 1 -> 2" in summary


def test_resolve_and_set_path():
    data = {"users": [{"name": "Bob"}]}
    assert resolve_path(data, ("users", 0, "name")) == "Bob"

    set_path(data, ("users", 0, "name"), "Robert")
    assert data["users"][0]["name"] == "Robert"

    set_path(data, ("config", "server", "port"), 8080)
    assert data["config"]["server"]["port"] == 8080
