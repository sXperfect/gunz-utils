"""Perpetual security & concurrency audit - PHASE 20 (round-3) regression tests.

Round-3 re-audit of plugins, faults, result, and project (the deepest deferred
/NEW issues two prior passes missed). Tests are written to FAIL ("red") against
the current source (base f0b3e98, which already contains the phase 1-19 fixes)
and must pass only after the corresponding production fix lands. Production
code is intentionally not modified.

Findings covered here (NEW, not previously flagged):

1. ``resolve_project_root`` (project.py re-export; canonical implementation in
   ext/project_gitpython.py:65-81) short-circuits nested git repositories via
   its process-global cache. Once an outer repository root is cached, a later
   call whose anchor lies at-or-below that root reuses the cached root without
   re-searching. If the anchor is inside a NESTED git repository (e.g. a
   submodule), the correct root is the nested repo's root, but the cache
   returns the outer root instead - a silent wrong result. Scripts that first
   resolve the main project and then operate on a submodule resolve the wrong
   root.

2. ``Result`` (result.py:29-35) exposes ``value`` and ``error`` as public
   dataclass fields, but the private ``_ok`` flag defaults to ``True``. A
   caller constructing ``Result(error=exc)`` through the public constructor
   gets ``ValueError("successful result cannot contain an error")`` instead of
   an error result; the public ``error`` field cannot be used without also
   setting the private ``_ok`` flag (or using the ``err()`` classmethod). The
   constructor should infer the active variant from which field is populated.

3. ``FaultyStream`` (faults.py:250) is documented as a "Binary stream wrapper"
   but does not implement the standard ``BinaryIO`` context-manager protocol
   (``__enter__``/``__exit__``) nor ``readinto``. Using it where a binary
   stream is expected - ``with FaultyStream(f) as fs`` or a ``readinto``-based
   reader - raises ``TypeError``/``AttributeError`` instead of delegating to
   the wrapped stream.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import io
import os
import pathlib
import shutil
import subprocess
import tempfile

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.faults import FaultyStream
from gunz_utils.result import Result

# -----------------------------------------------------------------------------
# project.py / ext/project_gitpython.py - cache short-circuits nested repos
# -----------------------------------------------------------------------------


def test_project_root_nested_repo_returns_inner_root() -> None:
    """RED: a nested git repo must resolve to its own root, not the outer one."""
    pytest.importorskip("git")
    if shutil.which("git") is None:
        pytest.skip("git CLI not available")

    import gunz_utils.ext.project_gitpython as project_gitpython

    project_gitpython._PROJECT_ROOT = None
    project_gitpython._PROJECT_ANCHOR = None

    with tempfile.TemporaryDirectory() as tmp:
        outer = os.path.join(tmp, "outer")
        os.makedirs(outer)
        subprocess.run(["git", "init", "-q", outer], check=True, capture_output=True)
        nested = os.path.join(outer, "nested")
        os.makedirs(nested)
        subprocess.run(["git", "init", "-q", nested], check=True, capture_output=True)

        resolve = project_gitpython.resolve_project_root
        outer_root = resolve(anchor=outer, inject_to_sys_path=False)
        inner_root = resolve(anchor=nested, inject_to_sys_path=False)

        assert pathlib.Path(nested).resolve() == inner_root
        assert inner_root != outer_root


# -----------------------------------------------------------------------------
# result.py - Result(error=...) cannot construct an error result
# -----------------------------------------------------------------------------


def test_result_public_error_field_constructs_error_result() -> None:
    """RED: Result(error=exc) must build an error result, not raise."""
    result = Result(error="boom")
    assert result.is_err
    assert not result.is_ok
    assert result.error == "boom"
    with pytest.raises(RuntimeError):
        result.unwrap()


def test_result_err_classmethod_unchanged() -> None:
    """Sanity green: Result.err(...) still builds a working error result."""
    result = Result.err("boom")
    assert result.is_err
    assert result.error == "boom"
    assert result.value is None


def test_result_ok_classmethod_unchanged() -> None:
    """Sanity green: Result.ok(...) still builds a working success result."""
    result = Result.ok(5)
    assert result.is_ok
    assert result.value == 5


def test_result_both_fields_set_still_rejected() -> None:
    """Sanity green: value and error set together must still be rejected."""
    with pytest.raises(ValueError):
        Result(value=5, error="boom", _ok=False)


# -----------------------------------------------------------------------------
# faults.py - FaultyStream lacks the BinaryIO context-manager protocol
# -----------------------------------------------------------------------------


def test_faulty_stream_supports_context_manager() -> None:
    """RED: FaultyStream must be usable as a binary-stream context manager."""
    buf = io.BytesIO(b"data")
    with FaultyStream(buf) as stream:
        stream.write(b"x")
    assert buf.closed


def test_faulty_stream_supports_readinto() -> None:
    """RED: FaultyStream must support readinto for BinaryIO consumers."""
    stream = FaultyStream(io.BytesIO(b"hello world"))
    out = bytearray(5)
    count = stream.readinto(out)
    assert count == 5
    assert bytes(out[:count]) == b"hello"


def test_faulty_stream_read_write_still_work() -> None:
    """Sanity green: plain read/write forwarding still behaves correctly."""
    stream = FaultyStream(io.BytesIO(b"hello"))
    assert stream.read() == b"hello"
    buf = io.BytesIO()
    out = FaultyStream(buf)
    assert out.write(b"abc") == 3
    assert buf.getvalue() == b"abc"
