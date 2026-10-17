# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import multiprocessing
import statistics
import sys
import time
from pathlib import Path
from typing import Any

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
    advisory_file_lock,
    match_path_glob,
    matches_any_glob,
    walk_files,
)
from gunz_utils.io import (
    physical_lines,
    read_file_snapshot,
    read_source_file,
)
from gunz_utils.plugins import (
    install_file_module_finder,
    load_module_from_path,
    make_file_module_name,
)
from gunz_utils.stats import (
    ECDFPoint,
    ParetoObjective,
    RunningStats,
    ecdf,
    pareto_dominates,
    pareto_frontier,
)

# =============================================================================
# PART 1: ADVISORY FILE LOCK
# =============================================================================


def test_advisory_file_lock_lifecycle(
    tmp_path: Path,
) -> None:
    lock_file = tmp_path / "test.lock"
    assert not lock_file.exists()

    with advisory_file_lock(lock_file) as locked:
        assert locked == lock_file
        assert lock_file.exists()
        assert lock_file.is_file()

    #? Re-acquisition succeeds
    with advisory_file_lock(lock_file) as locked2:
        assert locked2 == lock_file


def test_advisory_file_lock_invalid_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        with advisory_file_lock(""):
            pass

    with pytest.raises(ValueError, match="timeout"):
        with advisory_file_lock(tmp_path / "a.lock", timeout=-1.0):
            pass

    with pytest.raises(ValueError, match="timeout"):
        with advisory_file_lock(tmp_path / "a.lock", timeout=float("inf")):
            pass

    with pytest.raises(ValueError, match="shared"):
        with advisory_file_lock(tmp_path / "a.lock", shared="not_a_bool"):  # type: ignore[arg-type]
            pass

    with pytest.raises(ValueError, match="mode"):
        with advisory_file_lock(tmp_path / "a.lock", mode=-1):
            pass

    #? Symlink rejection
    target = tmp_path / "real.lock"
    target.write_text("x")
    sym = tmp_path / "sym.lock"
    sym.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        with advisory_file_lock(sym):
            pass


def _child_hold_lock(
    lock_path_str: str,
    ready_event: Any,
    release_event: Any,
) -> None:
    with advisory_file_lock(lock_path_str):
        ready_event.set()
        release_event.wait(timeout=5.0)


def test_advisory_file_lock_conflict_and_timeout(
    tmp_path: Path,
) -> None:
    lock_file = tmp_path / "conflict.lock"
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()

    proc = ctx.Process(target=_child_hold_lock, args=(str(lock_file), ready, release))
    proc.start()
    try:
        assert ready.wait(timeout=5.0), "child process failed to acquire lock in time"

        #? Non-blocking attempt should immediately raise TimeoutError
        with pytest.raises(TimeoutError):
            with advisory_file_lock(lock_file, timeout=0):
                pass

        #? Timed attempt should raise TimeoutError after elapsed duration
        t0 = time.monotonic()
        with pytest.raises(TimeoutError):
            with advisory_file_lock(lock_file, timeout=0.05):
                pass
        assert time.monotonic() - t0 >= 0.04
    finally:
        release.set()
        proc.join(timeout=5.0)

    #? After child exits, parent acquires immediately
    with advisory_file_lock(lock_file, timeout=1.0) as locked:
        assert locked == lock_file


# =============================================================================
# PART 2: GLOBBING & FILTERED DIRECTORY WALKING
# =============================================================================


def test_match_path_glob_basic() -> None:
    assert match_path_glob("a/b/c.py", "*.py")
    assert match_path_glob("a/b/c.py", "c.py")
    assert match_path_glob("a/b/c.py", "b/c.py")
    assert not match_path_glob("a/b/c.py", "d.py")
    assert not match_path_glob("", "*.py")
    assert not match_path_glob("a/b/c.py", "")


def test_match_path_glob_recursive_star_star() -> None:
    assert match_path_glob("tmp/build/log.txt", "tmp/**")
    assert match_path_glob("tmp/build/deep/nested/log.txt", "tmp/**")
    assert match_path_glob("src/gunz_utils/tests/test_io.py", "**/tests/**/test_*.py")
    assert match_path_glob("tests/test_io.py", "**/tests/**/test_*.py")
    assert match_path_glob("foo/bar/baz.txt", "**")
    assert match_path_glob("foo/bar/baz.txt", "foo/**/baz.txt")
    assert match_path_glob("foo/baz.txt", "foo/**/baz.txt")
    assert not match_path_glob("foo/bar/other.txt", "foo/**/baz.txt")


def test_match_path_glob_anchored() -> None:
    assert match_path_glob("a/b/c.py", "a/**", anchored=True)
    assert not match_path_glob("x/a/b/c.py", "a/**", anchored=True)
    assert match_path_glob("x/a/b/c.py", "a/**", anchored=False)


def test_match_path_glob_complex_polynomial() -> None:
    #? Multiple ** segments must evaluate in polynomial time without blowup
    pattern = "**/a/**/b/**/c/**/d.txt"
    path = "x/y/a/1/2/b/3/c/4/5/d.txt"
    assert match_path_glob(path, pattern)

    mismatch = "x/y/a/1/2/b/3/c/4/5/e.txt"
    assert not match_path_glob(mismatch, pattern)


def test_matches_any_glob() -> None:
    patterns = ["*.py", "*.md", "tmp/**"]
    assert matches_any_glob("README.md", patterns)
    assert matches_any_glob("src/main.py", patterns)
    assert matches_any_glob("tmp/sub/scratch.bin", patterns)
    assert not matches_any_glob("src/image.png", patterns)


def test_walk_files_pruning(
    tmp_path: Path,
) -> None:
    #? Create directory tree
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "a.py").write_text("print('a')")
    (tmp_path / "src" / "pkg" / "b.txt").write_text("text")

    (tmp_path / "node_modules" / "bad").mkdir(parents=True)
    (tmp_path / "node_modules" / "bad" / "lib.py").write_text("bad")

    (tmp_path / ".git" / "objects").mkdir(parents=True)
    (tmp_path / ".git" / "objects" / "pack.py").write_text("git")

    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs" / "index.md").write_text("# Docs")

    #? Walk with exclude
    files = list(
        walk_files(
            tmp_path,
            exclude=["node_modules/**", ".git/**"],
            extensions=[".py", ".md"],
        )
    )
    rel_files = [f.relative_to(tmp_path).as_posix() for f in files]
    assert rel_files == ["docs/index.md", "src/pkg/a.py"]

    #? NotADirectoryError on non-dir
    with pytest.raises(NotADirectoryError):
        list(walk_files(tmp_path / "does_not_exist"))


# =============================================================================
# PART 3: PHYSICAL LINES & CAS FILE SNAPSHOT
# =============================================================================


def test_physical_lines_preserves_unicode_separators() -> None:
    #? str.splitlines() splits on \u2028 LINE SEPARATOR and \u2029 PARAGRAPH SEPARATOR
    text = "line 1\nline 2 with \u2028 embedded unicode\r\nline 3\rline 4"

    py_split = text.splitlines()
    assert len(py_split) == 5

    custom_split = physical_lines(text)
    assert len(custom_split) == 4
    assert custom_split[0] == "line 1"
    assert custom_split[1] == "line 2 with \u2028 embedded unicode"
    assert custom_split[2] == "line 3"
    assert custom_split[3] == "line 4"

    #? keepends=True
    keepends_split = physical_lines(text, keepends=True)
    assert keepends_split[0] == "line 1\n"
    assert keepends_split[1] == "line 2 with \u2028 embedded unicode\r\n"
    assert keepends_split[2] == "line 3\r"
    assert keepends_split[3] == "line 4"

    assert physical_lines("") == []
    with pytest.raises(TypeError):
        physical_lines(123)  # type: ignore[arg-type]


def test_file_snapshot_write_if_unchanged(
    tmp_path: Path,
) -> None:
    f = tmp_path / "sample.txt"
    f.write_text("alpha\nbeta\n", encoding="utf-8")

    snapshot = read_file_snapshot(f)
    assert snapshot.text == "alpha\nbeta\n"
    assert snapshot.newline == "\n"
    assert snapshot.encoding == "utf-8"

    #? Identical content is a no-op
    snapshot.write_if_unchanged("alpha\nbeta\n")

    #? Change succeeds when file hasn't been modified
    snapshot.write_if_unchanged("alpha\nbeta\ngamma\n")
    assert f.read_text() == "alpha\nbeta\ngamma\n"

    #? Second write from the old snapshot fails because file was modified
    with pytest.raises(OSError, match="file changed"):
        snapshot.write_if_unchanged("overwrite attempt")


def test_read_source_file_encoding(
    tmp_path: Path,
) -> None:
    f = tmp_path / "iso_source.py"
    #? Write Python file with ISO-8859-1 declaration
    content = "# -*- coding: iso-8859-1 -*-\n# café\nfoo = 'bar'\n"
    f.write_bytes(content.encode("iso-8859-1"))

    snapshot = read_source_file(f)
    assert "iso-8859-1" in snapshot.encoding.lower()
    assert "café" in snapshot.text


# =============================================================================
# PART 4: STATISTICAL HELPERS (RunningStats, Pareto, ECDF)
# =============================================================================


def test_running_stats_empty() -> None:
    stats = RunningStats()
    assert stats.count == 0
    assert math.isclose(stats.mean, 0.0, abs_tol=1e-9)
    assert math.isclose(stats.variance, 0.0, abs_tol=1e-9)
    assert math.isclose(stats.stdev, 0.0, abs_tol=1e-9)
    assert math.isclose(stats.total, 0.0, abs_tol=1e-9)
    assert math.isnan(stats.minimum)
    assert math.isnan(stats.maximum)


def test_running_stats_accuracy() -> None:
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    stats = RunningStats.from_iterable(data)

    assert stats.count == len(data)
    assert math.isclose(stats.mean, statistics.mean(data))
    assert math.isclose(stats.variance, statistics.variance(data))
    assert math.isclose(stats.stdev, statistics.stdev(data))
    assert math.isclose(stats.pvariance, statistics.pvariance(data))
    assert math.isclose(stats.pstdev, statistics.pstdev(data))
    assert math.isclose(stats.minimum, 2.0, abs_tol=1e-9)
    assert math.isclose(stats.maximum, 9.0, abs_tol=1e-9)
    assert math.isclose(stats.total, sum(data))


def test_running_stats_parallel_merge() -> None:
    data_a = [1.0, 3.0, 5.0, 7.0, 9.0]
    data_b = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    all_data = data_a + data_b

    stats_a = RunningStats.from_iterable(data_a)
    stats_b = RunningStats.from_iterable(data_b)

    merged = stats_a.merge(stats_b)

    assert merged.count == len(all_data)
    assert math.isclose(merged.mean, statistics.mean(all_data))
    assert math.isclose(merged.variance, statistics.variance(all_data))
    assert math.isclose(merged.stdev, statistics.stdev(all_data))
    assert math.isclose(merged.minimum, min(all_data), abs_tol=1e-9)
    assert math.isclose(merged.maximum, max(all_data), abs_tol=1e-9)
    assert math.isclose(merged.total, sum(all_data))


def test_running_stats_invalid_inputs() -> None:
    stats = RunningStats()
    with pytest.raises(TypeError):
        stats.update("invalid")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        stats.update(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        stats.update(float("nan"))
    with pytest.raises(ValueError):
        stats.update(float("inf"))
    with pytest.raises(TypeError):
        stats.merge("not_stats")  # type: ignore[arg-type]


def test_pareto_dominance_and_frontier() -> None:
    #? 2 objectives: (latency, memory); both lower is better
    objs = [
        ParetoObjective("latency", lower_is_better=True),
        ParetoObjective("memory", lower_is_better=True),
    ]

    p1 = (10.0, 100.0)
    p2 = (5.0, 50.0)  #? dominates p1 (better in both)
    p3 = (20.0, 40.0)  #? trade-off: higher latency, lower memory

    assert pareto_dominates(p2, p1, objs)
    assert not pareto_dominates(p1, p2, objs)
    assert not pareto_dominates(p2, p3, objs)
    assert not pareto_dominates(p3, p2, objs)

    items = [
        {"name": "A", "metrics": (10.0, 100.0)},
        {"name": "B", "metrics": (5.0, 50.0)},
        {"name": "C", "metrics": (20.0, 40.0)},
    ]

    frontier = pareto_frontier(items, key=lambda x: x["metrics"], objectives=objs)
    frontier_names = [x["name"] for x in frontier]
    assert frontier_names == ["B", "C"]  #? A is dominated by B


def test_ecdf_exact() -> None:
    data = [1.0, 2.0, 2.0, 3.0]
    points = ecdf(data)

    assert len(points) == 3
    assert isinstance(points[0], ECDFPoint)
    assert math.isclose(points[0].value, 1.0, abs_tol=1e-9)
    assert math.isclose(points[0].probability, 0.25, abs_tol=1e-9)
    assert points[0].count == 1

    assert math.isclose(points[1].value, 2.0, abs_tol=1e-9)
    assert math.isclose(points[1].probability, 0.75, abs_tol=1e-9)
    assert points[1].count == 2

    assert math.isclose(points[2].value, 3.0, abs_tol=1e-9)
    assert math.isclose(points[2].probability, 1.0, abs_tol=1e-9)
    assert points[2].count == 1


# =============================================================================
# PART 5: DYNAMIC MODULE DISCOVERY & TRANSACTIONAL LOADING
# =============================================================================


def test_module_from_path_and_meta_path(
    tmp_path: Path,
) -> None:
    script = tmp_path / "sample_worker.py"
    script.write_text("def compute(x):\n    return x * 42\nVALUE = 100\n")

    mod = load_module_from_path(script)
    assert mod.compute(2) == 84
    assert mod.VALUE == 100

    mod_name = make_file_module_name(script)
    assert mod_name in sys.modules
    assert sys.modules[mod_name] is mod

    #? Finder can resolve the module spec
    finder = install_file_module_finder()
    spec = finder.find_spec(mod_name, None)
    assert spec is not None
    assert spec.origin == str(script.resolve())


def test_module_from_path_transactional_rollback(
    tmp_path: Path,
) -> None:
    failing_script = tmp_path / "broken_plugin.py"
    failing_script.write_text("var = 1\nraise RuntimeError('boom')\n")

    mod_name = make_file_module_name(failing_script)
    assert mod_name not in sys.modules

    with pytest.raises(RuntimeError, match="boom"):
        load_module_from_path(failing_script)

    #? Must be rolled back from sys.modules
    assert mod_name not in sys.modules
