"""Tests for Wave 5 Sub-Wave 5: Filesystem Operations, Advisory Locking & Temp
Resources.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import tempfile
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.filesystem import (
    TemporaryDirectoryPool,
    advisory_file_lock,
    copy_file_atomic,
    ensure_directory,
    file_size_bytes,
    find_files,
    get_disk_usage,
    is_file_locked,
    safe_remove,
    safe_rmtree,
    touch_file,
    walk_directory,
)


def test_ensure_directory_and_touch_file():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sub = base / "a" / "b"
        res = ensure_directory(sub)
        assert res.is_dir()

        f = sub / "test.txt"
        touch_file(f)
        assert f.is_file()
        assert file_size_bytes(f) == 0

        #? update touch
        touch_file(f)
        assert f.is_file()


def test_safe_remove_and_safe_rmtree():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        f = base / "sample.txt"
        assert not safe_remove(f)
        f.write_text("data")
        assert safe_remove(f)
        assert not f.exists()

        d = base / "dir_to_remove"
        d.mkdir()
        (d / "nested.txt").write_text("nested")
        assert safe_rmtree(d)
        assert not d.exists()
        assert not safe_rmtree(d, missing_ok=True)


def test_copy_file_atomic():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        src = base / "src.txt"
        src.write_text("hello world")
        dst = base / "sub" / "dst.txt"

        copied = copy_file_atomic(src, dst)
        assert copied.is_file()
        assert copied.read_text() == "hello world"


def test_find_files_and_walk_directory():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "a.py").write_text("12345")
        (base / "b.txt").write_text("12")
        (base / "c.py").write_text("1234567890")

        all_files = list(walk_directory(base))
        assert len(all_files) == 3

        py_files = list(find_files(base, pattern="*.py"))
        assert len(py_files) == 2

        sized = list(find_files(base, min_size=3, max_size=8))
        assert len(sized) == 1
        assert sized[0].name == "a.py"


def test_advisory_file_lock_and_is_file_locked():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        lock_path = base / "test.lock"

        assert not is_file_locked(lock_path)
        with advisory_file_lock(lock_path):
            assert is_file_locked(lock_path)
        assert not is_file_locked(lock_path)


def test_get_disk_usage():
    with tempfile.TemporaryDirectory() as tmp:
        total, used, free = get_disk_usage(tmp)
        assert total > 0
        assert free > 0
        assert total >= free


def test_temporary_directory_pool():
    pool = TemporaryDirectoryPool(max_dirs=2)
    with pool.acquire() as d1:
        assert d1.is_dir()
        (d1 / "test.txt").write_text("temp data")
    #? returned to pool
    with pool.acquire() as d2:
        assert d2.is_dir()
        #? verify cleaned
        assert not (d2 / "test.txt").exists()
    pool.cleanup()
