"""Darwin ABI preparation and separately guarded actual POSIX/Darwin probes.

Fake libc dispatch proves Python adapter behavior only, never a macOS kernel.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path
from types import SimpleNamespace
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

from gunz_utils import fs
from gunz_utils.security import open_path_under_base


class _RenameShim:
    def __init__(self,
        error: int = 0,
    ) -> None:
        self.error = error
        self.calls: list[tuple[bytes, bytes, int]] = []
        self.argtypes: list[Any] | None = None
        self.restype: Any = None

    def __call__(self,
        source: bytes,
        target: bytes,
        flags: int,
    ) -> int:
        self.calls.append((source, target, flags))
        ctypes.set_errno(self.error)
        return -1 if self.error else 0


def _darwin_dispatch_shim(
    monkeypatch: pytest.MonkeyPatch,
    function: _RenameShim | None,
) -> None:
    if os.name == "nt":
        pytest.skip("Darwin adapter preparation requires the POSIX dispatch branch")
    library = SimpleNamespace()
    if function is not None:
        library.renamex_np = function
    monkeypatch.setattr(fs.sys, "platform", "darwin")
    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: library)


def test_darwin_adapter_requests_exclusive_flag_and_correct_c_abi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    function = _RenameShim()
    _darwin_dispatch_shim(monkeypatch, function)
    source, target = tmp_path / "source-é", tmp_path / "target-é"
    fs._rename_directory_noreplace(source, target)
    assert function.calls == [(os.fsencode(source), os.fsencode(target), 0x00000004)]
    assert function.argtypes == [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    assert function.restype == ctypes.c_int
    #? The fake ABI has deliberately performed no kernel rename.
    assert not source.exists()
    assert not target.exists()


@pytest.mark.parametrize("error", [errno.ENOSYS, errno.EINVAL, errno.ENOTSUP])
def test_darwin_unsupported_adapter_fails_closed_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: int,
) -> None:
    function = _RenameShim(error)
    _darwin_dispatch_shim(monkeypatch, function)

    def forbidden_replace(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise AssertionError("unsupported exclusive rename must not use os.replace")

    monkeypatch.setattr(fs.os, "replace", forbidden_replace)
    target = tmp_path / "published"
    with pytest.raises(NotImplementedError, match="does not support"):
        with fs.transactional_directory(target) as staging:
            (staging / "data").write_bytes(b"candidate")
    assert len(function.calls) == 1
    assert not target.exists()
    assert list(tmp_path.glob(".published.*")) == []


def test_darwin_missing_symbol_never_uses_nonexclusive_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _darwin_dispatch_shim(monkeypatch, None)
    with pytest.raises(NotImplementedError, match="unavailable"):
        with fs.transactional_directory(tmp_path / "published") as staging:
            (staging / "data").write_bytes(b"candidate")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("error", [errno.EEXIST, errno.EXDEV, errno.EACCES])
def test_darwin_adapter_preserves_meaningful_errno(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: int,
) -> None:
    function = _RenameShim(error)
    _darwin_dispatch_shim(monkeypatch, function)
    with pytest.raises(OSError) as raised:
        fs._rename_directory_noreplace(tmp_path / "source", tmp_path / "target")
    assert raised.value.errno == error
    assert raised.value.filename == str(tmp_path / "target")
    if error == errno.EEXIST:
        assert isinstance(raised.value, FileExistsError)


@pytest.mark.skipif(os.name != "posix", reason="actual POSIX descriptor probe")
def test_actual_posix_descriptor_read_refuses_intermediate_symlink(
    tmp_path: Path,
) -> None:
    required = (os.open, os.stat, os.mkdir, os.link, os.unlink, os.rename)
    assert all(operation in os.supports_dir_fd for operation in required)
    assert hasattr(os, "O_DIRECTORY")
    assert hasattr(os, "O_NOFOLLOW")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "data").write_bytes(b"independent regular-file oracle")
    with open_path_under_base(str(tmp_path), "nested/data") as handle:
        assert handle.read() == b"independent regular-file oracle"
    (tmp_path / "alias").symlink_to(nested, target_is_directory=True)
    with pytest.raises(OSError):
        open_path_under_base(str(tmp_path), "alias/data")


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires actual Darwin renamex_np"
)
def test_native_darwin_volume_exclusive_directory_rename(
    tmp_path: Path,
) -> None:
    assert getattr(ctypes.CDLL(None), "renamex_np", None) is not None
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "payload").write_bytes(b"native directory oracle")
    source_inode, target_inode = source.stat().st_ino, target.stat().st_ino
    try:
        with pytest.raises(FileExistsError):
            fs._rename_directory_noreplace(source, target)
    except NotImplementedError:
        assert source.is_dir() and target.is_dir()
        pytest.skip("this real Darwin volume does not support RENAME_EXCL")
    assert source.stat().st_ino == source_inode
    assert target.stat().st_ino == target_inode
    assert list(target.iterdir()) == []
    target.rmdir()
    fs._rename_directory_noreplace(source, target)
    assert not source.exists()
    assert target.stat().st_ino == source_inode
    assert (target / "payload").read_bytes() == b"native directory oracle"


@pytest.mark.skipif(
    sys.platform != "darwin", reason="requires actual Darwin fsync/modes"
)
def test_native_darwin_private_atomic_write_and_directory_fsync(
    tmp_path: Path,
) -> None:
    from gunz_utils.io import atomic_write

    target = tmp_path / "secret"
    atomic_write(
        target, b"synthetic private bytes", mode="wb", durable=True, permissions=0o600
    )
    assert target.read_bytes() == b"synthetic private bytes"
    assert target.stat().st_mode & 0o777 == 0o600
