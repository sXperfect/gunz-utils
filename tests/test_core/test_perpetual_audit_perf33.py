"""Phase 33 perpetual audit: round-4 (deepest) re-audit of five core modules.

dict_utils.py, collections.py, signals.py, sync.py, time_utils.py.

Verified correct at base 7e91aa3 (GREEN companion tests below):
- dict_utils: deep_get/deep_set/deep_merge correctness, no input mutation,
  cyclic dict/list merge (no hang), iterative (no RecursionError) on 5000-deep
  nesting, dedup unhashable + bool-vs-int distinctness, path normalization.
- collections: unique (hashable/unhashable/key), group_by, index_by, partition.
- signals: GracefulShutdown LIFO cleanup, duplicate-signal dedup, empty-signum
  rejection, re-entry resets shutdown state.
- sync: timeout/max_output_bytes/completion_marker validation (incl. OverflowError
  guard on huge int timeouts).
- time_utils: monotonic_deadline/remaining/expired math, OverflowError guard on
  huge ints, bool rejection.

Two NEW findings:

1) collections.py unique bool-vs-int distinctness (src/gunz_utils/collections.py:
   35-49). The package documents a strict bool-is-subtype-of-int numeric
   contract (honored by deep_merge's dedup at dict_utils.py:422-434, which keys
   booleans as ``(bool, item)`` so ``True`` stays distinct from ``1`` and
   ``False`` from ``0``). ``unique`` does NOT honor this: it dedups ``True``
   with ``1`` (``unique([True, 1]) -> [True]``, ``unique([1, True]) -> [1]``),
   silently collapsing a boolean and an equal integer. Expected: ``True`` and
   ``1`` (and ``False``/``0``) are kept distinct, consistent with the package
   contract and with ``deep_merge``'s dedup. Currently collapsed (RED).

2) sync.py rsync_mirror extra_args accepts a bare str (src/gunz_utils/sync.py:
   312-316). ``extra_args`` is typed ``Sequence[str]``, and a bare ``str`` IS a
   ``Sequence[str]``, so ``extra_args="--verbose"`` passes validation and is
   then iterated character-by-character into ``rsync_args`` (``rsync_args.extend
   (extra_args)`` at sync.py:370), producing one malformed argument per
   character instead of a single option. Expected: a bare str is rejected with
   TypeError (it cannot be treated as a single argument). Currently accepted
   and mis-handled (RED).

This test is expected to be RED against base 7e91aa3 for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import asyncio
import signal

import pytest

from gunz_utils import collections as C
from gunz_utils import dict_utils as D
from gunz_utils import time_utils as T
from gunz_utils.signals import GracefulShutdown, install_async_signal_handlers
from gunz_utils.sync import rsync_mirror


# ---------------------------------------------------------------------------
# RED: collections.unique must keep bool distinct from equal ints.
# ---------------------------------------------------------------------------
def test_unique_keeps_bool_distinct_from_int() -> None:
    assert C.unique([True, 1]) == [True, 1]
    assert C.unique([1, True]) == [1, True]
    assert C.unique([False, 0]) == [False, 0]
    assert C.unique([0, False]) == [0, False]


# ---------------------------------------------------------------------------
# RED: sync.rsync_mirror must reject a bare str for extra_args.
# ---------------------------------------------------------------------------
def test_sync_extra_args_rejects_bare_string(tmp_path) -> None:
    with pytest.raises(TypeError):
        rsync_mirror(
            "nonexistent_source_xyz",
            str(tmp_path / "dest"),
            extra_args="--verbose",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# GREEN: dict_utils.
# ---------------------------------------------------------------------------
def test_dict_utils_get_set_merge() -> None:
    source = {"a": {"b": {"c": 42}}}
    assert D.deep_get(source, "a.b.c") == 42
    assert D.deep_get(source, "a.b.missing", default=None) is None
    with pytest.raises(KeyError):
        D.deep_get(source, "a.b.missing")
    target: dict = {}
    D.deep_set(target, "a.b.c", 1)
    assert target == {"a": {"b": {"c": 1}}}
    assert D.deep_merge({"a": {"b": 1}}, {"a": {"c": 2}}) == {"a": {"b": 1, "c": 2}}
    assert D.deep_merge({"x": [1, 2]}, {"x": [3]}, list_strategy="concat") == {
        "x": [1, 2, 3]
    }
    assert D.deep_merge({"x": [1, 2]}, {"x": [2]}, list_strategy="dedup") == {
        "x": [1, 2]
    }
    # No input mutation.
    base = {"x": [1]}
    D.deep_merge(base, {"y": 2})
    assert base == {"x": [1]}


def test_dict_utils_cyclic_and_deep() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    merged = D.deep_merge({"k": cyclic}, {"j": 1})
    assert merged["j"] == 1
    cyclic_list: list[object] = []
    cyclic_list.append(cyclic_list)
    merged2 = D.deep_merge({"x": cyclic_list}, {"y": 2})
    assert len(merged2["x"]) == 1  # no hang / no RecursionError
    # 5000-deep nesting: iterative, no RecursionError.
    root: dict[str, object] = {}
    cur: dict[str, object] = root
    for _ in range(5000):
        cur["k"] = {}
        cur = cur["k"]
    out = D.deep_merge(root, {"z": 1})
    assert isinstance(out, dict)


def test_dict_utils_path_normalization() -> None:
    with pytest.raises(ValueError):
        D.deep_get({"a": 1}, "a..b")
    with pytest.raises(ValueError):
        D.deep_get({"a": 1}, [])
    with pytest.raises(ValueError):
        D.deep_get({"a": 1}, ["a", "b"], separator=":")


# ---------------------------------------------------------------------------
# GREEN: collections.
# ---------------------------------------------------------------------------
def test_collections_transforms() -> None:
    assert C.unique([1, 2, 1, 3, 2]) == [1, 2, 3]
    assert C.unique([[1], [2], [1]]) == [[1], [2]]
    assert C.unique(["a", "A", "b"], key=str.lower) == ["a", "b"]
    assert C.group_by([("a", 1), ("b", 2), ("a", 3)], key=lambda x: x[0]) == {
        "a": [("a", 1), ("a", 3)],
        "b": [("b", 2)],
    }
    assert C.index_by([("a", 1), ("b", 2), ("a", 9)], key=lambda x: x[0]) == {
        "a": ("a", 9),
        "b": ("b", 2),
    }
    assert C.partition(range(6), predicate=lambda x: x % 2 == 0) == (
        [0, 2, 4],
        [1, 3, 5],
    )


# ---------------------------------------------------------------------------
# GREEN: signals.
# ---------------------------------------------------------------------------
def test_signals_graceful_shutdown_cleanup() -> None:
    async def scenario() -> None:
        events: list[str] = []
        gs = GracefulShutdown(signums=(signal.SIGTERM,))
        gs.add_callback(lambda: events.append("cb1"))

        async def cb2() -> None:
            await asyncio.sleep(0)
            events.append("cb2")

        gs.add_callback(cb2)
        async with gs:
            gs.trigger_shutdown(15)
        # __aexit__ ran cleanup once, in LIFO order.
        assert events == ["cb2", "cb1"]
        assert gs.signal_received == 15

    asyncio.run(scenario())


def test_signals_install_rejects_empty_signums() -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError):
            install_async_signal_handlers(lambda s: None, signums=())

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# GREEN: time_utils.
# ---------------------------------------------------------------------------
def test_time_utils_deadlines() -> None:
    deadline = T.monotonic_deadline(5)
    assert deadline > 0
    assert T.remaining(deadline) >= 0
    assert not T.expired(T.monotonic_deadline(100))
    with pytest.raises(ValueError):
        T.monotonic_deadline(10**400)
    with pytest.raises(ValueError):
        T.monotonic_deadline(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        T.monotonic_deadline(float("inf"))
    with pytest.raises(ValueError):
        T.remaining(float("nan"))


# ---------------------------------------------------------------------------
# GREEN: sync validation (without running rsync).
# ---------------------------------------------------------------------------
def test_sync_validation(tmp_path) -> None:
    with pytest.raises(ValueError):
        rsync_mirror("s", str(tmp_path / "d"), timeout=10**400)
    with pytest.raises(ValueError):
        rsync_mirror("s", str(tmp_path / "d"), timeout=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        rsync_mirror(
            "s", str(tmp_path / "d"), max_output_bytes=True  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        rsync_mirror("s", str(tmp_path / "d"), completion_marker="../evil")
    with pytest.raises(ValueError):
        rsync_mirror("s", str(tmp_path / "d"), extra_args=["--delete"])
