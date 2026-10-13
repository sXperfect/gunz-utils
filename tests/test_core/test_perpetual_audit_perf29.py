"""Phase 29 perpetual audit: round-4 (deepest) re-audit of five core modules.

collections.py, dict_utils.py, env.py, signals.py, and sync.py were verified
correct across targeted probes: unique/group_by/index_by/partition incl.
unhashable dedup and key handling; deep_get/deep_set/deep_merge (no input
mutation, cyclic merge, dedup-unhashable, bool-vs-int dedup, iterative
stack-safe deep nesting); env cast/whitespace/unset/finiteness handling;
sync _unsafe_rsync_extra_argument destructive-option and abbreviation
rejection (incl. --delete, --del, -e/-f/-M/-T, --temp, --backup-dir, resets).

Two NEW real bugs surfaced:

1. env.py ``env_bool`` does not validate that ``default`` is a bool. The
   signature is ``default: bool | object = _MISSING`` and the return type is
   ``bool``, but a caller-supplied non-bool default (e.g. ``"yes"``) is
   returned verbatim when the variable is unset, violating the strict-boolean
   contract and producing a non-bool value downstream.

2. signals.py ``GracefulShutdown`` leaks stale shutdown state across context
   re-entry. ``trigger_shutdown`` sets ``_shutdown_event`` once; a subsequent
   ``async with`` on the same object does not reset it, so exiting a fresh
   block that never shut down still runs ``run_cleanup`` (spurious cleanup).

This test is expected to be RED against base ``8bca900`` for both cases and
documents the correct behavior after a fix.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from gunz_utils.collections import group_by, index_by, partition, unique
from gunz_utils.dict_utils import deep_get, deep_merge, deep_set
from gunz_utils.env import env, env_bool
from gunz_utils.signals import GracefulShutdown
from gunz_utils.sync import _unsafe_rsync_extra_argument


# ---------------------------------------------------------------------------
# RED: env_bool must not silently return a non-bool default.
# ---------------------------------------------------------------------------
def test_env_bool_rejects_non_bool_default() -> None:
    os.environ.pop("PERF29_UNSET", None)
    assert env_bool("PERF29_UNSET", default=True) is True
    assert env_bool("PERF29_UNSET", default=False) is False
    # A non-bool default violates the strict-boolean contract and must be
    # rejected rather than returned verbatim.
    with pytest.raises(ValueError):
        env_bool("PERF29_UNSET", default="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        env_bool("PERF29_UNSET", default=1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED: GracefulShutdown must not run cleanup on a fresh re-entered context that
# never shut down (stale shutdown event leaks across blocks).
# ---------------------------------------------------------------------------
def test_graceful_shutdown_reuse_does_not_leak_shutdown_state() -> None:
    async def main() -> None:
        gs = GracefulShutdown(timeout=1.0)
        cleanup_runs: list[int] = []

        def cleanup() -> None:
            cleanup_runs.append(1)

        gs.add_callback(cleanup)
        # First block triggers shutdown -> cleanup runs.
        async with gs:
            gs.trigger_shutdown()
        assert len(cleanup_runs) == 1
        # Re-enter the same object; this block never shuts down and is not
        # cancelled, so cleanup must NOT run again.
        async with gs:
            pass
        assert len(cleanup_runs) == 1, (
            "reusing a GracefulShutdown must reset stale shutdown state; "
            "cleanup ran on a block that never shut down"
        )

    asyncio.run(main())


# ---------------------------------------------------------------------------
# GREEN: collections.
# ---------------------------------------------------------------------------
def test_collections() -> None:
    assert unique([1, 2, 1, 3, 2]) == [1, 2, 3]
    assert unique(["a", "b", "A"], key=str.lower) == ["a", "b"]
    assert unique([[1], [2], [1]]) == [[1], [2]]
    assert group_by(range(6), key=lambda x: x % 2) == {0: [0, 2, 4], 1: [1, 3, 5]}
    assert index_by([("a", 1), ("b", 2), ("a", 3)], key=lambda x: x[0]) == {
        "a": ("a", 3),
        "b": ("b", 2),
    }
    assert partition(range(6), predicate=lambda x: x % 2 == 0) == ([0, 2, 4], [1, 3, 5])


# ---------------------------------------------------------------------------
# GREEN: dict_utils.
# ---------------------------------------------------------------------------
def test_dict_utils() -> None:
    assert deep_get({"a": {"b": 1}}, "a.b") == 1
    assert deep_get({"a": {"b": 1}}, "a.c", default=None) is None
    with pytest.raises(KeyError):
        deep_get({"a": 1}, "a.b")
    target: dict = {}
    deep_set(target, "a.b.c", 42)
    assert target == {"a": {"b": {"c": 42}}}

    base = {"a": {"b": [1, 2]}, "xs": [1]}
    ovr = {"a": {"c": [3]}, "xs": [2]}
    res = deep_merge(base, ovr, list_strategy="concat")
    assert res["a"] == {"b": [1, 2], "c": [3]}
    assert res["xs"] == [1, 2]
    # Inputs are not mutated.
    assert base == {"a": {"b": [1, 2]}, "xs": [1]}
    assert ovr == {"a": {"c": [3]}, "xs": [2]}
    # Dedup (bool vs int stay distinct; unhashable dedup works).
    assert deep_merge({"xs": [1, 2, 3]}, {"xs": [2, 4]}, list_strategy="dedup")[
        "xs"
    ] == [1, 2, 3, 4]
    assert deep_merge({"xs": [1, True]}, {"xs": [True, 0]}, list_strategy="dedup")[
        "xs"
    ] == [1, True, 0]
    with pytest.raises(ValueError):
        deep_merge({}, {}, list_strategy="bogus")


# ---------------------------------------------------------------------------
# GREEN: env parsing correctness.
# ---------------------------------------------------------------------------
def test_env_parse_correctness() -> None:
    os.environ["PERF29_SET"] = "  42  "
    assert env("PERF29_SET", cast=int) == 42
    os.environ["PERF29_BOOL"] = "TRUE"
    assert env_bool("PERF29_BOOL") is True
    os.environ.pop("PERF29_MISSING", None)
    assert env("PERF29_MISSING", default="d") == "d"
    os.environ["PERF29_WS"] = "   "
    assert env("PERF29_WS", default=7) == 7  # whitespace-only -> default
    os.environ["PERF29_NAN"] = "nan"
    with pytest.raises(ValueError):
        env("PERF29_NAN", cast=float)
    os.environ["PERF29_INF"] = "1e400"
    with pytest.raises(ValueError):
        env("PERF29_INF", cast=float)
    with pytest.raises(KeyError):
        env("PERF29_DEFINITELY_UNSET_XYZ")


# ---------------------------------------------------------------------------
# GREEN: sync unsafe-option rejection (security filter).
# ---------------------------------------------------------------------------
def test_sync_unsafe_option_rejection() -> None:
    unsafe = [
        "--delete",
        "--delete-excluded",
        "--del",
        "--partial-dir=x",
        "--temp",
        "--rsync-path=x",
        "--files-from=x",
        "-e",
        "-f",
        "-M",
        "-T",
        "--filter=x",
        "--backup-dir=x",
        "--exclude=!",
        "--",
    ]
    for arg in unsafe:
        assert _unsafe_rsync_extra_argument(arg) is True, arg
    safe = [
        "--partial",
        "--backup",
        "--include=*",
        "--exclude=*",
        "--exclude=!x",
        "-a",
        "-avz",
    ]
    for arg in safe:
        assert _unsafe_rsync_extra_argument(arg) is False, arg
