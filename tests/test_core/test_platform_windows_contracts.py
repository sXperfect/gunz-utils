"""Windows build preparation and explicitly native-only kernel contracts."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
import multiprocessing
import os
import subprocess
import sys
from multiprocessing.connection import Connection
from pathlib import Path
from types import ModuleType, SimpleNamespace

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest


def _builder() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "windows_build", root / "scripts/build_native.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("compiler_status", [0, 2])
def test_windows_build_preparation_matches_abi_and_cleans_intermediates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    debug: bool,
    compiler_status: int,
) -> None:
    """Capture argv only: this is preparation, never evidence of an MSVC build."""
    module = _builder()
    base = tmp_path / "base interpreter"
    libraries = base / "libs"
    libraries.mkdir(parents=True)
    tag = f"{sys.version_info.major}{sys.version_info.minor}"
    library = libraries / f"python{tag}{'_d' if debug else ''}.lib"
    library.write_bytes(b"synthetic import-library placeholder")
    output = tmp_path / "isolated package with spaces"
    captured: list[tuple[list[str], Path]] = []

    def config(
        name: str,
    ) -> object:
        suffix = f"{'_d' if debug else ''}.cp{tag}-win_amd64.pyd"
        return {"EXT_SUFFIX": suffix, "Py_DEBUG": int(debug)}.get(name)

    def compiler(
        command: list[str],
        *,
        check: bool,
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[bytes]:
        assert not check and cwd is not None
        captured.append((command, cwd.resolve()))
        for name in ("_accel.obj", "_accel.lib", "_accel.exp"):
            (cwd / name).write_bytes(b"synthetic intermediate")
        if compiler_status == 0:
            path = Path(next(arg[3:] for arg in command if arg.startswith("/Fe")))
            path.write_bytes(b"synthetic final artifact, not executable")
        return subprocess.CompletedProcess(command, compiler_status)

    with monkeypatch.context() as scoped:
        #? Model this case's interpreter independently of a real debug host.
        scoped.setattr(
            module,
            "sys",
            SimpleNamespace(
                platform="win32",
                base_prefix=str(base),
                version_info=sys.version_info,
                stderr=sys.stderr,
            ),
        )
        scoped.chdir(tmp_path)
        scoped.setattr(module.sysconfig, "get_config_var", config)
        scoped.setattr(
            module.sysconfig, "get_paths", lambda: {"include": str(base / "Include")}
        )
        scoped.setattr(module.subprocess, "run", compiler)
        requested_output = output.relative_to(tmp_path) if debug else output
        assert module.build(requested_output) == compiler_status
    assert len(captured) == 1
    command, intermediate = captured[0]
    assert command[0] == "cl" and "/LD" in command
    assert ("/MDd" if debug else "/MD") in command
    assert str(library) in command
    expected_name = f"_accel{'_d' if debug else ''}.cp{tag}-win_amd64.pyd"
    assert (
        Path(next(arg[3:] for arg in command if arg.startswith("/Fe"))).name
        == expected_name
    )
    assert f"/LIBPATH:{libraries}" in command[command.index("/link") + 1 :]
    assert (
        Path(next(arg[3:] for arg in command if arg.startswith("/Fo"))).parent
        == intermediate
    )
    assert (
        Path(
            next(arg.split(":", 1)[1] for arg in command if arg.startswith("/IMPLIB:"))
        ).parent
        == intermediate
    )
    assert not intermediate.exists()
    assert sorted(path.suffix for path in output.iterdir()) == (
        [".pyd"] if compiler_status == 0 else []
    )


def test_windows_debug_marker_without_metadata_uses_matching_debug_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows metadata need not expose Py_DEBUG; its debug marker still governs ABI."""
    module = _builder()
    base = tmp_path / "debug interpreter"
    libraries = base / "libs"
    libraries.mkdir(parents=True)
    tag = f"{sys.version_info.major}{sys.version_info.minor}"
    library = libraries / f"python{tag}_d.lib"
    library.write_bytes(b"synthetic debug import library")
    commands: list[list[str]] = []

    def compiler(
        command: list[str],
        *,
        check: bool,
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[bytes]:
        assert not check and cwd is not None
        commands.append(command)
        return subprocess.CompletedProcess(command, 2)

    with monkeypatch.context() as scoped:
        scoped.setattr(
            module,
            "sys",
            SimpleNamespace(
                platform="win32",
                base_prefix=str(base),
                version_info=sys.version_info,
                stderr=sys.stderr,
                gettotalrefcount=lambda: 0,
            ),
        )
        scoped.setattr(
            module.sysconfig,
            "get_config_var",
            lambda name: f"_d.cp{tag}-win_amd64.pyd" if name == "EXT_SUFFIX" else None,
        )
        scoped.setattr(
            module.sysconfig,
            "get_paths",
            lambda: {"include": str(base / "Include")},
        )
        scoped.setattr(module.subprocess, "run", compiler)
        assert module.build(tmp_path / "output") == 2
    assert len(commands) == 1
    assert "/MDd" in commands[0] and "/MD" not in commands[0]
    assert str(library) in commands[0]
    assert Path(next(arg[3:] for arg in commands[0] if arg.startswith("/Fe"))).name == (
        f"_accel_d.cp{tag}-win_amd64.pyd"
    )
    assert str(libraries / f"python{tag}.lib") not in commands[0]
    assert not list((tmp_path / "output").iterdir())


def test_windows_missing_base_import_library_does_not_launch_compiler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _builder()
    calls: list[object] = []
    with monkeypatch.context() as scoped:
        scoped.setattr(module.sys, "platform", "win32")
        scoped.setattr(module.sys, "base_prefix", str(tmp_path / "missing-base"))
        scoped.setattr(module.sysconfig, "get_config_var", lambda name: None)
        scoped.setattr(
            module.sysconfig,
            "get_paths",
            lambda: {"include": str(tmp_path / "missing-base/Include")},
        )
        scoped.setattr(
            module.subprocess, "run", lambda *args, **kwargs: calls.append(args)
        )
        assert module.build(tmp_path / "output") == 1
    assert not calls
    assert "CPython import library is missing" in capsys.readouterr().err
    assert not list((tmp_path / "output").iterdir())


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_posix_build_preparation_keeps_compiler_flags_and_output_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    module = _builder()
    calls: list[list[str]] = []

    def compiler(
        command: list[str],
        *,
        check: bool,
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[bytes]:
        assert not check and cwd is None
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    with monkeypatch.context() as scoped:
        scoped.setattr(module.sys, "platform", platform)
        scoped.delenv("CC", raising=False)
        scoped.setattr(module.sysconfig, "get_config_var", lambda name: ".test.so")
        scoped.setattr(
            module.sysconfig,
            "get_paths",
            lambda: {"include": str(tmp_path / "python-includes")},
        )
        scoped.setattr(module.subprocess, "run", compiler)
        assert module.build(tmp_path / "output") == 0
    assert calls[0][0] == ("clang" if platform == "darwin" else "gcc")
    assert calls[0][1:4] == ["-O3", "-shared", "-fPIC"]
    assert "-o" in calls[0] and "/link" not in calls[0]
    assert (calls[0][-2:] == ["-undefined", "dynamic_lookup"]) == (platform == "darwin")


def _windows_holder(
    channel: Connection,
    base: str,
) -> None:
    from gunz_utils.ext.secure_store import SecureStore

    try:
        with SecureStore(base_dir=base) as store:
            store.unlock()
            with store._coordination_lock:
                channel.send("held")
                if not channel.poll(15):
                    raise TimeoutError("bounded parent release deadline")
                channel.recv()
    finally:
        channel.close()


@pytest.mark.skipif(
    sys.platform != "win32", reason="actual Windows CRT byte lock required"
)
@pytest.mark.parametrize("exit_kind", ["release", "terminate"])
def test_windows_byte_lock_serializes_and_releases_on_holder_exit(
    tmp_path: Path,
    exit_kind: str,
) -> None:
    #? Runtime import keeps Linux typechecking from assuming Windows CRT symbols.
    msvcrt = importlib.import_module("msvcrt")

    from gunz_utils.ext.secure_store import SecureStore, _unlock_fd

    with SecureStore(base_dir=tmp_path) as seed:
        seed.unlock()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_windows_holder, args=(child, str(tmp_path)))
    descriptor = -1
    try:
        process.start()
        child.close()
        assert parent.poll(15) and parent.recv() == "held"
        descriptor = os.open(tmp_path / ".lock", os.O_RDWR)
        os.lseek(descriptor, 0, os.SEEK_SET)
        with pytest.raises(OSError):
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        if exit_kind == "release":
            parent.send("release")
        else:
            process.terminate()
        process.join(5)
        assert not process.is_alive()
        assert (
            process.exitcode == 0 if exit_kind == "release" else process.exitcode != 0
        )
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        _unlock_fd(descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
                process.join(3)
            if process.is_alive():
                process.kill()
                process.join(3)
            assert not process.is_alive()
            process.close()
        child.close()
        parent.close()


@pytest.mark.skipif(sys.platform != "win32", reason="actual Windows rename required")
def test_windows_directory_rename_preserves_existing_target(
    tmp_path: Path,
) -> None:
    from gunz_utils.fs import _rename_directory_noreplace

    source, target = tmp_path / "staging", tmp_path / "competing"
    source.mkdir()
    target.mkdir()
    (source / "payload").write_bytes(b"synthetic staged bytes")
    with pytest.raises(FileExistsError):
        _rename_directory_noreplace(source, target)
    assert target.is_dir() and not list(target.iterdir())
    assert (source / "payload").read_bytes() == b"synthetic staged bytes"


@pytest.mark.skipif(
    sys.platform != "win32", reason="actual Windows store filesystem required"
)
@pytest.mark.parametrize("passphrase", [None, "synthetic-windows-passphrase"])
def test_windows_store_roundtrip_and_mode_cleanup(
    tmp_path: Path,
    passphrase: str | None,
) -> None:
    from gunz_utils.ext.secure_store import SecureStore

    switched = "synthetic-switched-passphrase" if passphrase is None else None
    with SecureStore(base_dir=tmp_path) as store:
        store.unlock(passphrase)
        store.set("secret", "synthetic-value", acl=["reader"], caller="reader")
        store.rotate_master_key(switched, allow_mode_switch=True)
        assert (tmp_path / "master.key").exists() == (switched is None)
        assert (tmp_path / "master.salt").exists() == (switched is not None)
    with SecureStore(base_dir=tmp_path) as reopened:
        reopened.unlock(switched)
        assert reopened.verify_integrity()
        assert reopened.get("secret", caller="reader") == "synthetic-value"
        with pytest.raises(PermissionError):
            reopened.get("secret", caller="outsider")
