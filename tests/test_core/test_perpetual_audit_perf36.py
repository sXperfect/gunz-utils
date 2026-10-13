"""Phase 36 perpetual audit: round-4 (deepest) re-audit of five core modules.

config.py, fs.py, subprocess.py, structures.py, result.py.

Verified correct at base 70d55f4 (GREEN companion tests below):
- config: env_overrides prefix/nested/separator/collision/empty-segment/
  scalar-conflict handling; merge_configs layering.
- fs: contained_path, lexical_contained_path, atomic_write_bytes roundtrip,
  transactional_directory publish/cleanup.
- subprocess: run_command output/returncode, check=True CommandError,
  CommandOutputLimitError, TimeoutError, args/output-limit validation.
- structures: RingBuffer, top_k, deep_diff, freeze_structure, stable_unique
  (int dedup), retain_priority_and_recent.
- result: ok/err/is_ok/is_err/unwrap/unwrap_or/map/map_error and validation.

Two NEW findings:

1) subprocess.py _validate_timeout_value (src/gunz_utils/subprocess.py:86)
   leaks OverflowError for huge int timeouts. The guard
   ``math.isfinite(float(value))`` calls ``float(value)`` on the raw value
   before any overflow protection, so a finite integer not representable as
   float (e.g. ``10**400``) raises ``OverflowError: int too large to convert
   to float`` instead of the documented ``ValueError`` ("timeout must be a
   finite non-negative number or None"). This is the recurring unguarded-float
   OverflowError leak (already fixed for network/resilience/upstream in phase
   30) now present in subprocess.py's timeout and terminate_grace validation,
   reachable via both ``run_command`` and ``run_command_async`` (RED).

2) structures.py stable_unique (src/gunz_utils/structures.py:99-103) drops
   distinct bool/int values. It dedups with a plain ``set`` membership test, so
   ``True == 1`` and ``False == 0`` collapse: ``stable_unique([True, 1, False,
   0])`` returns ``[True, False]``, silently discarding the ``1`` and ``0``.
   This violates the package's bool-is-subtype-of-int dedup contract, which
   ``collections.unique`` honors (it keys bools as ``(bool, marker)`` and
   returns ``[True, 1, False, 0]``). ``stable_unique`` must keep bool and int
   distinct to match the package-wide contract (RED).

This test is expected to be RED against base 70d55f4 for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import asyncio

import pytest
from gunz_utils import config as C
from gunz_utils import fs as F
from gunz_utils import result as R
from gunz_utils import structures as S
from gunz_utils import subprocess as SP

config = C
fs = F
structures = S
subprocess = SP


def _run(coro: object) -> object:  # pragma: no cover - trivial helper
    return asyncio.run(coro)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED: subprocess unguarded-float OverflowError leak.
# ---------------------------------------------------------------------------
def test_run_command_timeout_huge_int_is_value_error() -> None:
    with pytest.raises(ValueError):
        SP.run_command(["true"], timeout=10**400)


def test_run_command_async_timeout_huge_int_is_value_error() -> None:
    async def go() -> None:
        with pytest.raises(ValueError):
            await SP.run_command_async(["true"], timeout=10**400)

    _run(go())


def test_validate_timeout_value_huge_int_is_value_error() -> None:
    with pytest.raises(ValueError):
        SP._validate_timeout_value(10**400, name="timeout")
    with pytest.raises(ValueError):
        SP._validate_timeout_value(10**400, name="terminate_grace")


# ---------------------------------------------------------------------------
# RED: stable_unique drops distinct bool/int values.
# ---------------------------------------------------------------------------
def test_stable_unique_keeps_bool_and_int_distinct() -> None:
    assert list(S.stable_unique([True, 1, False, 0])) == [True, 1, False, 0]


# ---------------------------------------------------------------------------
# GREEN: subprocess companion behaviors.
# ---------------------------------------------------------------------------
def test_run_command_success_output_and_returncode() -> None:
    result = SP.run_command(["sh", "-c", "printf hi"])
    assert result.returncode == 0
    assert result.stdout == "hi"
    assert result.duration >= 0


def test_run_command_check_raises_command_error() -> None:
    with pytest.raises(SP.CommandError):
        SP.run_command(["false"], check=True)


def test_run_command_output_limit_raises() -> None:
    with pytest.raises(SP.CommandOutputLimitError):
        SP.run_command(
            ["sh", "-c", "printf 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'"],
            max_output_bytes=10,
        )


def test_run_command_timeout_raises() -> None:
    with pytest.raises(TimeoutError):
        SP.run_command(["sleep", "2"], timeout=0.1)


def test_run_command_validates_args_and_output_limit() -> None:
    with pytest.raises(TypeError):
        SP.run_command("true")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SP.run_command([])
    with pytest.raises(ValueError):
        SP.run_command(["true"], max_output_bytes=-1)
    with pytest.raises(ValueError):
        SP.run_command(["true"], max_output_bytes=True)


# ---------------------------------------------------------------------------
# GREEN: config companion behaviors.
# ---------------------------------------------------------------------------
def test_env_overrides_nested_and_separator() -> None:
    environ = {"APP_DB__HOST": "h", "APP_DB__PORT": "1", "OTHER": "x"}
    out = config.env_overrides(environ, prefix="APP")
    assert out == {"db": {"host": "h", "port": "1"}}


def test_env_overrides_custom_separator() -> None:
    out = config.env_overrides({"APP:DB:HOST": "h"}, prefix="APP", separator=":")
    assert out == {"db": {"host": "h"}}


def test_env_overrides_case_insensitive_collision_raises() -> None:
    with pytest.raises(ValueError):
        config.env_overrides({"APP_DB": "a", "app_db": "b"}, prefix="APP")


def test_env_overrides_scalar_conflict_raises() -> None:
    with pytest.raises(ValueError):
        config.env_overrides(
            {"APP_DB": "x", "APP_DB__HOST": "h"},
            prefix="APP",
        )


def test_env_overrides_empty_segment_raises_and_prefix_validation() -> None:
    with pytest.raises(ValueError):
        config.env_overrides({"APP_A__B": "v"}, prefix="APP", separator="_")
    with pytest.raises(ValueError):
        config.env_overrides({}, prefix="")
    with pytest.raises(ValueError):
        config.env_overrides({}, prefix="APP", separator="")


def test_merge_configs_layering() -> None:
    out = config.merge_configs({"a": {"x": 1}}, {"a": {"y": 2}, "b": 3})
    assert out == {"a": {"x": 1, "y": 2}, "b": 3}


# ---------------------------------------------------------------------------
# GREEN: fs companion behaviors.
# ---------------------------------------------------------------------------
def test_contained_path_inside_and_outside(tmp_path: pytest.TempPathFactory) -> None:
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "sub" / "f.txt"
    inside.parent.mkdir(parents=True)
    inside.write_text("x")
    assert F.contained_path(root, "sub/f.txt") == inside.resolve()
    with pytest.raises(ValueError):
        F.contained_path(root, "../outside")


def test_lexical_contained_path_rejects_absolute_and_parent(
    tmp_path: pytest.TempPathFactory,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError):
        F.lexical_contained_path(root, "/etc/passwd")
    with pytest.raises(ValueError):
        F.lexical_contained_path(root, "a/../b")


def test_atomic_write_bytes_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "out.bin"
    F.atomic_write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_transactional_directory_publishes(tmp_path: pytest.TempPathFactory) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "out"
    with F.transactional_directory(target) as staging:
        (staging / "f.txt").write_text("data")
    assert (target / "f.txt").read_text() == "data"


# ---------------------------------------------------------------------------
# GREEN: structures companion behaviors.
# ---------------------------------------------------------------------------
def test_ring_buffer_capacity() -> None:
    buf = S.RingBuffer(3)
    for value in range(5):
        buf.append(value)
    assert list(buf) == [2, 3, 4]
    assert len(buf) == 3


def test_top_k() -> None:
    assert S.top_k([1, 5, 3, 9, 2], 2) == [9, 5]
    with pytest.raises(ValueError):
        S.top_k([1], -1)


def test_stable_unique_int_dedup_preserves_order() -> None:
    assert list(S.stable_unique([2, 1, 2, 3, 1])) == [2, 1, 3]
    assert list(S.stable_unique([])) == []


def test_deep_diff_scalar_and_mapping() -> None:
    diffs = S.deep_diff({"a": 1, "b": 2}, {"a": 1, "b": 3})
    assert [d.kind for d in diffs] == ["value"]
    assert diffs[0].path == "b"
    missing = S.deep_diff({"a": 1}, {"a": 1, "b": 2})
    assert missing[0].kind == "missing_left"


def test_deep_diff_sequence_length() -> None:
    diffs = S.deep_diff([1, 2], [1, 2, 3])
    assert diffs[0].kind == "length"


def test_deep_diff_cycle_terminates() -> None:
    a: list[object] = []
    a.append(a)
    b: list[object] = []
    b.append(b)
    assert S.deep_diff(a, b) == []


def test_freeze_structure_and_cycle() -> None:
    frozen = S.freeze_structure({"a": [1, 2]})
    assert frozen["a"] == (1, 2)
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError):
        S.freeze_structure(cyclic)


def test_retain_priority_and_recent() -> None:
    items = ["p1", "n1", "n2", "n3", "p2"]
    out = S.retain_priority_and_recent(
        items,
        is_priority=lambda item: item.startswith("p"),
        max_recent=2,
    )
    assert out == ["p1", "n2", "n3", "p2"]


# ---------------------------------------------------------------------------
# GREEN: result companion behaviors.
# ---------------------------------------------------------------------------
def test_result_ok_err_and_predicates() -> None:
    ok = R.Result.ok(5)
    err = R.Result.err("boom")
    assert ok.is_ok and not ok.is_err
    assert err.is_err and not err.is_ok
    assert ok.unwrap() == 5
    assert err.unwrap_or(0) == 0


def test_result_map_and_map_error() -> None:
    ok = R.Result.ok(2)
    assert ok.map(lambda x: x * 3).unwrap() == 6
    err = R.Result.err("bad")
    mapped = err.map(lambda x: x)
    assert mapped.is_err
    err_upper = err.map_error(str.upper)
    assert err_upper.is_err
    assert err_upper.error == "BAD"  # type: ignore[union-attr]


def test_result_validation() -> None:
    with pytest.raises(ValueError):
        R.Result(value=1, error=2)
    with pytest.raises(ValueError):
        R.Result(value=1, _ok=False)
