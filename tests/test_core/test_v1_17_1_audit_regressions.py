"""Adversarial regression tests for the v1.17.1 deep security and algorithm audit."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import os
import sys
from fractions import Fraction
from pathlib import Path

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import stats
from gunz_utils.fs import (
    advisory_file_lock,
    tree_fingerprint,
    walk_files,
)
from gunz_utils.io import read_file_snapshot
from gunz_utils.plugins import (
    GunzFileFinder,
    load_module_from_path,
    make_file_module_name,
)
from gunz_utils.stats import (
    ParetoObjective,
    RunningStats,
    pareto_dominates,
    pareto_frontier,
    summarize,
)


def test_native_fast_summary_and_running_stats_do_not_leak_refcounts() -> None:
    sample = [10.5, 20.25, 30.75, 40.125, 50.5, 1000.0]
    pcts = (0.25, 0.5, 0.75)

    #? When native acceleration is active, verify raw dict items have no extra C ref
    if stats._accel_fast_summary is not None:
        raw = stats._accel_fast_summary(sample, pcts, 3.5)
        assert raw is not None
        expected_keys = (
            "minimum",
            "maximum",
            "mean",
            "median",
            "variance",
            "stdev",
            "mad",
            "percentiles",
            "outlier_indices",
        )
        for key in expected_keys:
            val = raw[key]
            #? 1 ref in `raw` + 1 ref in `val` + 1 ref for getrefcount arg = 3
            assert sys.getrefcount(val) == 3, f"leaked refcount on {key}"

    def workload() -> None:
        for _ in range(128):
            res = summarize(sample, percentiles=pcts)
            assert res.count == 6
            acc = RunningStats()
            acc.extend(sample)
            assert acc.count == 6

    workload()
    before = (
        sys.getrefcount(sample),
        sys.getrefcount(pcts),
        tuple(sys.getrefcount(x) for x in sample),
    )
    workload()
    after = (
        sys.getrefcount(sample),
        sys.getrefcount(pcts),
        tuple(sys.getrefcount(x) for x in sample),
    )
    assert after == before


def test_summarize_near_zero_mean_cv_parity_and_fraction_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    #? Mean is ~3.33e-17, which is within abs_tol=1e-15 of 0.0
    near_zero = [-1.0, 1.0, 1e-16]
    res_active = summarize(near_zero)
    assert res_active.coefficient_of_variation is None

    monkeypatch.setattr(stats, "_accel_fast_summary", None)
    res_py = summarize(near_zero)
    assert res_py.coefficient_of_variation is None

    #? Exact Fraction instances are Real and must work identically in both backends
    frac_samples = [Fraction(1, 2), Fraction(3, 2), Fraction(5, 2)]
    frac_summary = summarize(frac_samples)
    assert math.isclose(frac_summary.mean, 1.5, rel_tol=1e-12)
    rs = RunningStats.from_iterable(frac_samples)
    assert rs.count == 3
    assert math.isclose(rs.mean, 1.5, rel_tol=1e-12)

    #? Booleans in percentiles must be rejected
    with pytest.raises(ValueError, match="percentile q must be finite"):
        summarize([1.0, 2.0, 3.0], percentiles=[True])
    with pytest.raises(ValueError, match="percentile q must be finite"):
        summarize([1.0, 2.0, 3.0], percentiles=[False])


def test_running_stats_extend_failure_atomicity_and_overflow() -> None:
    rs = RunningStats.from_iterable([1.0, 2.0, 3.0])
    snap = rs.to_dict()

    #? Sequence with trailing NaN must not partially mutate rs
    with pytest.raises(ValueError, match="finite"):
        rs.extend([4.0, 5.0, float("nan")])
    assert rs.to_dict() == snap

    #? Generator with trailing invalid type must not partially mutate rs
    with pytest.raises(TypeError, match="real numeric"):
        rs.extend(x for x in [4.0, True])  # type: ignore[misc]
    assert rs.to_dict() == snap

    #? Extreme values that overflow M2 must raise OverflowError atomically
    rs_extreme = RunningStats.from_iterable([-1e308])
    with pytest.raises(OverflowError, match="overflowed"):
        rs_extreme.update(1e308)
    assert rs_extreme.count == 1

    rs_other = RunningStats.from_iterable([1e308])
    with pytest.raises(OverflowError, match="overflowed"):
        rs_extreme.merge(rs_other)


def test_pareto_sub_1e15_scale_oracle_equivalence_and_preconditions() -> None:
    objs_2d = [
        ParetoObjective("x", lower_is_better=True),
        ParetoObjective("y", lower_is_better=True),
    ]
    #? Points separated by 5e-16: a=(0.0, 1.0) and b=(5e-16, 0.5) are non-dominated
    candidates: list[tuple[str, tuple[float, float]]] = [
        ("a", (0.0, 1.0)),
        ("b", (5e-16, 0.5)),
        ("c", (5e-16, 0.8)),
        ("d", (1e-15, 0.2)),
    ]
    expected_2d = [
        item
        for item in candidates
        if not any(
            pareto_dominates(other[1], item[1], objs_2d) for other in candidates
        )
    ]
    actual_2d = pareto_frontier(candidates, key=lambda x: x[1], objectives=objs_2d)
    assert actual_2d == expected_2d
    assert [name for name, _ in actual_2d] == ["a", "b", "d"]

    #? 1D sub-1e-15 distinction
    objs_1d = [ParetoObjective("x", lower_is_better=True)]
    pts_1d = [("best", (0.0,)), ("worse", (5e-16,))]
    assert pareto_frontier(pts_1d, key=lambda x: x[1], objectives=objs_1d) == [
        ("best", (0.0,))
    ]

    #? Preconditions: empty objectives must fail even when items is empty
    with pytest.raises(ValueError, match="at least one objective"):
        pareto_frontier([], key=lambda x: x, objectives=[])

    #? Booleans as objective coordinates must be rejected
    with pytest.raises(TypeError, match="real numeric"):
        pareto_dominates([True, 1.0], [0.0, 1.0], objs_2d)
    with pytest.raises(TypeError, match="real numeric"):
        pareto_frontier([("bad", (False, 1.0))], key=lambda x: x[1], objectives=objs_2d)


def test_file_snapshot_write_if_unchanged_detects_mutation_on_noop_payload(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tracked.txt"
    target.write_text("original\n", encoding="utf-8")

    snap = read_file_snapshot(target, max_bytes=1024)
    assert snap.text == "original\n"

    with pytest.raises(TypeError, match="durable must be bool"):
        snap.write_if_unchanged("original\n", durable="invalid")  # type: ignore[arg-type]

    #? Mutate file externally, then pass the OLD text (payload == snap.raw)
    target.write_text("externally modified\n", encoding="utf-8")
    with pytest.raises(OSError, match="file changed before modification"):
        snap.write_if_unchanged("original\n")


def test_plugins_gunz_file_finder_and_load_module_reject_symlinks_and_non_regular(
    tmp_path: Path,
) -> None:
    #? Passing a directory must raise ValueError (not FileNotFoundError)
    with pytest.raises(ValueError, match="regular file"):
        load_module_from_path(tmp_path)

    real_mod = tmp_path / "real_mod.py"
    real_mod.write_text("X = 7\n", encoding="utf-8")
    sym_mod = tmp_path / "sym_mod.py"
    sym_mod.symlink_to(real_mod)

    finder = GunzFileFinder()
    #? Construct synthetic name pointing to symlinked path without resolving
    sym_hex = str(sym_mod.absolute()).encode("utf-8").hex()
    assert finder.find_spec(f"_gunz_file_{sym_hex}", None) is None

    #? Directory encoded in synthetic name must return None
    dir_hex = str(tmp_path.resolve()).encode("utf-8").hex()
    assert finder.find_spec(f"_gunz_file_{dir_hex}", None) is None

    #? Relative path encoded in synthetic name must return None
    rel_hex = b"relative/mod.py".hex()
    assert finder.find_spec(f"_gunz_file_{rel_hex}", None) is None

    #? Invalid prefix or reload type
    with pytest.raises(ValueError, match="valid Python identifier"):
        make_file_module_name(real_mod, prefix="123-bad")
    with pytest.raises(TypeError, match="reload must be bool"):
        load_module_from_path(real_mod, reload="yes")  # type: ignore[arg-type]


def test_walk_files_eager_validation_and_tree_fingerprint_pre1970_mtime(
    tmp_path: Path,
) -> None:
    #? Eager validation without iterating the returned generator
    with pytest.raises(NotADirectoryError):
        walk_files(tmp_path / "missing_dir")
    with pytest.raises(ValueError, match="max_depth"):
        walk_files(tmp_path, max_depth=-1)
    with pytest.raises(TypeError, match="follow_symlinks must be bool"):
        walk_files(tmp_path, follow_symlinks="yes")  # type: ignore[arg-type]

    #? Pre-1970 negative mtime_ns in tree_fingerprint
    ancient = tmp_path / "ancient.py"
    ancient.write_text("x = 1\n", encoding="utf-8")
    os.utime(ancient, (-86400, -86400))
    digest1 = tree_fingerprint(tmp_path)
    digest2 = tree_fingerprint(tmp_path)
    assert len(digest1) == 64
    assert digest1 == digest2

    #? Unsupported hash algorithm rejected
    with pytest.raises(ValueError, match="unsupported algorithm"):
        tree_fingerprint(tmp_path, algorithm="shake_128")

    #? Precondition validation in advisory_file_lock before filesystem touch
    missing_sub = tmp_path / "should_not_be_created" / "lockfile"
    with pytest.raises(ValueError, match="timeout"):
        with advisory_file_lock(missing_sub, timeout=-1.0):
            pass
    assert not missing_sub.parent.exists()
