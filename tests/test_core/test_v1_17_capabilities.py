# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import time
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

from gunz_utils.fs import (
    tree_fingerprint,
    walk_files,
)
from gunz_utils.io import (
    read_file_snapshot,
    read_source_file,
)
from gunz_utils.plugins import (
    load_module_from_path,
)
from gunz_utils.stats import (
    ParetoObjective,
    RunningStats,
    pareto_frontier,
    summarize,
)

# =============================================================================
# TRACK 1 & 2: PARETO FRONTIER SPEED & EXACTNESS
# =============================================================================


def test_pareto_frontier_1d() -> None:
    objs = [ParetoObjective("cost", lower_is_better=True)]
    items = [
        {"id": 1, "cost": 5.0},
        {"id": 2, "cost": 2.0},
        {"id": 3, "cost": 2.0},
        {"id": 4, "cost": 8.0},
    ]
    res = pareto_frontier(items, key=lambda x: [x["cost"]], objectives=objs)
    assert [x["id"] for x in res] == [2, 3]


def test_pareto_frontier_2d_sweep() -> None:
    objs = [
        ParetoObjective("latency", lower_is_better=True),
        ParetoObjective("memory", lower_is_better=True),
    ]
    #? Points:
    #? A: (10, 100) -> dominated by B (5, 50)
    #? B: (5, 50)   -> frontier
    #? C: (20, 30)  -> frontier (higher latency, lower memory)
    #? D: (15, 60)  -> dominated by B (5 < 15, 50 < 60)
    #? E: (25, 20)  -> frontier (lowest memory)
    items = [
        {"name": "A", "pt": (10.0, 100.0)},
        {"name": "B", "pt": (5.0, 50.0)},
        {"name": "C", "pt": (20.0, 30.0)},
        {"name": "D", "pt": (15.0, 60.0)},
        {"name": "E", "pt": (25.0, 20.0)},
    ]
    frontier = pareto_frontier(
        items, key=lambda x: x["pt"], objectives=objs
    )
    names = [x["name"] for x in frontier]
    assert names == ["B", "C", "E"]


def test_pareto_frontier_3d() -> None:
    objs = [
        ParetoObjective("f1", lower_is_better=True),
        ParetoObjective("f2", lower_is_better=True),
        ParetoObjective("f3", lower_is_better=True),
    ]
    items = [
        {"name": "p1", "metrics": (1.0, 5.0, 5.0)},
        {"name": "p2", "metrics": (5.0, 1.0, 5.0)},
        {"name": "p3", "metrics": (5.0, 5.0, 1.0)},
        {"name": "p4", "metrics": (6.0, 6.0, 6.0)},  #? dominated by all
    ]
    frontier = pareto_frontier(
        items, key=lambda x: x["metrics"], objectives=objs
    )
    assert [x["name"] for x in frontier] == ["p1", "p2", "p3"]


# =============================================================================
# TRACK 1 & 2: DIRECTORY WALKING HARDENING (max_depth & cycle detection)
# =============================================================================


def test_walk_files_max_depth(
    tmp_path: Path,
) -> None:
    #? Create nested structure:
    #? root/file0.txt (depth 0)
    #? root/d1/file1.txt (depth 1)
    #? root/d1/d2/file2.txt (depth 2)
    (tmp_path / "file0.txt").write_text("0")
    (tmp_path / "d1" / "d2").mkdir(parents=True)
    (tmp_path / "d1" / "file1.txt").write_text("1")
    (tmp_path / "d1" / "d2" / "file2.txt").write_text("2")

    #? depth 0: only top-level files
    d0_files = [
        f.name for f in walk_files(tmp_path, max_depth=0)
    ]
    assert d0_files == ["file0.txt"]

    #? depth 1: files up to d1
    d1_files = sorted(
        f.name for f in walk_files(tmp_path, max_depth=1)
    )
    assert d1_files == ["file0.txt", "file1.txt"]

    #? Invalid max_depth
    with pytest.raises(ValueError, match="max_depth"):
        list(walk_files(tmp_path, max_depth=-1))


def test_walk_files_symlink_cycle_protection(
    tmp_path: Path,
) -> None:
    #? Create directory with symlink pointing to ancestor
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "file.txt").write_text("hello")
    loop = sub / "loop"
    try:
        loop.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported on this platform")

    #? follow_symlinks=True must not loop infinitely
    files = list(walk_files(tmp_path, follow_symlinks=True))
    assert len(files) >= 1
    assert any(f.name == "file.txt" for f in files)


# =============================================================================
# TRACK 3: TREE STAT FINGERPRINTING
# =============================================================================


def test_tree_fingerprint_deterministic(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.py").write_text("print('hello')")
    (tmp_path / "b.txt").write_text("sample")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("x = 1")

    fp1 = tree_fingerprint(tmp_path)
    fp2 = tree_fingerprint(tmp_path)
    assert fp1 == fp2
    assert len(fp1) == 64

    #? Filter by extension
    py_fp = tree_fingerprint(tmp_path, extensions=[".py"])
    assert py_fp != fp1

    #? Modifying file timestamp changes fingerprint
    time.sleep(0.01)
    (tmp_path / "a.py").write_text("print('modified')")
    fp3 = tree_fingerprint(tmp_path)
    assert fp3 != fp1


# =============================================================================
# TRACK 2: BOUNDED ADMISSION READS IN SNAPSHOTS
# =============================================================================


def test_read_file_snapshot_max_bytes(
    tmp_path: Path,
) -> None:
    f = tmp_path / "data.bin"
    f.write_bytes(b"A" * 1024)

    #? Bounded read within limit succeeds
    snap = read_file_snapshot(f, max_bytes=2048)
    assert len(snap.raw) == 1024

    #? Bounded read exceeding limit fails
    with pytest.raises(ValueError, match="exceeds size limit"):
        read_file_snapshot(f, max_bytes=512)

    #? Invalid max_bytes values
    with pytest.raises(ValueError, match="max_bytes"):
        read_file_snapshot(f, max_bytes=0)
    with pytest.raises(ValueError, match="max_bytes"):
        read_file_snapshot(f, max_bytes=-10)


def test_read_source_file_max_bytes(
    tmp_path: Path,
) -> None:
    f = tmp_path / "script.py"
    f.write_text("print('test')\n", encoding="utf-8")

    snap = read_source_file(f, max_bytes=100)
    assert "print" in snap.text

    with pytest.raises(ValueError, match="exceeds size limit"):
        read_source_file(f, max_bytes=4)


# =============================================================================
# TRACK 2: PLUGIN LOADER HARDENING
# =============================================================================


def test_load_module_from_path_symlink_rejection(
    tmp_path: Path,
) -> None:
    target = tmp_path / "real_module.py"
    target.write_text("FOO = 42\n")
    sym = tmp_path / "sym_module.py"
    try:
        sym.symlink_to(target)
    except OSError:
        pytest.skip("symlinks not supported on this platform")

    with pytest.raises(ValueError, match="symbolic link"):
        load_module_from_path(sym)


# =============================================================================
# TRACK 1: RUNNING STATS & SUMMARIZE PARITY
# =============================================================================


def test_running_stats_and_summarize_consistency() -> None:
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    stats = RunningStats()
    stats.extend(data)

    assert stats.count == 10
    assert math.isclose(stats.mean, 5.5, abs_tol=1e-9)
    assert math.isclose(stats.minimum, 1.0, abs_tol=1e-9)
    assert math.isclose(stats.maximum, 10.0, abs_tol=1e-9)

    summary = summarize(data)
    assert summary.count == 10
    assert math.isclose(summary.mean, 5.5, abs_tol=1e-9)
    assert math.isclose(summary.median, 5.5, abs_tol=1e-9)
    assert math.isclose(summary.minimum, 1.0, abs_tol=1e-9)
    assert math.isclose(summary.maximum, 10.0, abs_tol=1e-9)
