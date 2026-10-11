"""Descriptor ownership across atomic-write setup failures."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import errno
import os
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

from gunz_utils import io


@pytest.mark.parametrize("failure", ["fchmod", "fdopen"])
def test_setup_failure_closes_reserved_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    if failure == "fchmod" and not hasattr(os, "fchmod"):
        pytest.skip("descriptor permissions unavailable")
    target = tmp_path / "existing.txt"
    target.write_text("original", encoding="utf-8")
    captured: list[int] = []
    real_mkstemp = io.tempfile.mkstemp

    def capture(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[int, str]:
        fd, path = real_mkstemp(*args, **kwargs)
        captured.append(fd)
        return fd, path

    error = OSError(errno.EIO, "synthetic setup failure")

    def fail(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise error

    monkeypatch.setattr(io.tempfile, "mkstemp", capture)
    monkeypatch.setattr(io.os, failure, fail)
    with pytest.raises(OSError) as raised:
        io.atomic_write(
            target, "replacement", permissions=0o600 if failure == "fchmod" else None
        )
    assert raised.value is error
    assert len(captured) == 1
    with pytest.raises(OSError) as closed:
        os.fstat(captured[0])
    assert closed.value.errno == errno.EBADF
    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [target]


def test_encoding_setup_failure_keeps_descriptor_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("original", encoding="utf-8")
    captured: list[int] = []
    real_fdopen = io.os.fdopen

    def inspect_wrapper(
        fd: int,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        captured.append(fd)
        assert kwargs["closefd"] is False
        try:
            return real_fdopen(fd, *args, **kwargs)
        except LookupError:
            #? Wrapper failure must not release/reuse the raw fd before our
            #? cleanup executes. This uses actual CPython encoding setup.
            os.fstat(fd)
            raise

    monkeypatch.setattr(io.os, "fdopen", inspect_wrapper)
    with pytest.raises(LookupError):
        io.atomic_write(target, "replacement", encoding="synthetic-invalid-codec")
    with pytest.raises(OSError) as closed:
        os.fstat(captured[0])
    assert closed.value.errno == errno.EBADF
    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [target]
