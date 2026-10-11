"""Finite independent-process sync lock/marker interruption proofs."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import multiprocessing
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.subprocess import CommandResult
from gunz_utils.sync import _unsafe_rsync_extra_argument, rsync_mirror


def _receive(
    pipe: Connection,
) -> tuple[Any, ...]:
    if not pipe.poll(8):
        raise TimeoutError("synthetic sync worker acknowledgement expired")
    return cast(tuple[Any, ...], pipe.recv())


def _sync_worker(
    root: str,
    pipe: Connection,
    observe: bool,
    hold_marker: bool,
) -> None:
    import gunz_utils.sync as module

    base = Path(root)
    target = base / "target"
    marker = target / ".gunz-sync-complete"
    original_lock = module._advisory_lock
    original_write = module.atomic_write

    @contextmanager
    def observed_lock(
        path: Path,
    ) -> Iterator[None]:
        if observe:
            pipe.send(("lock_attempt",))
        with original_lock(path):
            if observe:
                pipe.send(("lock_acquired",))
            yield

    def synthetic_run(
        args: list[str],
        **kwargs: Any,
    ) -> CommandResult:
        pipe.send(("running", marker.exists()))
        if _receive(pipe) != ("complete",):
            raise ValueError("unexpected synthetic transfer command")
        return CommandResult(tuple(args), 0, "", "", 0.01)

    def observed_write(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        result = original_write(*args, **kwargs)
        if hold_marker:
            pipe.send(("published", marker.read_text()))
            if _receive(pipe) != ("return",):
                raise ValueError("unexpected synthetic marker command")
        return result

    try:
        pipe.send(("ready",))
        if _receive(pipe) != ("start",):
            raise ValueError("unexpected synthetic worker command")
        with (
            patch.object(module.shutil, "which", return_value="synthetic-rsync"),
            patch.object(module, "_advisory_lock", observed_lock),
            patch.object(module, "run_command", synthetic_run),
            patch.object(module, "atomic_write", observed_write),
        ):
            module.rsync_mirror(base / "source", target)
        pipe.send(("done",))
    finally:
        pipe.close()


@pytest.mark.skipif(os.name != "posix", reason="sync requires real POSIX flock")
def test_real_sync_lock_covers_marker_and_recovers_after_transfer_process_death(
    tmp_path: Path,
) -> None:
    (tmp_path / "source").mkdir()
    target = tmp_path / "target"
    target.mkdir()
    marker = target / ".gunz-sync-complete"
    marker.write_text("old success\n")
    context = multiprocessing.get_context("spawn")
    children: list[tuple[Any, Connection]] = []

    def start(
        observe: bool,
        hold_marker: bool,
    ) -> tuple[Any, Connection]:
        parent, child = context.Pipe()
        process = context.Process(
            target=_sync_worker, args=(str(tmp_path), child, observe, hold_marker)
        )
        process.start()
        child.close()
        children.append((process, parent))
        assert _receive(parent) == ("ready",)
        parent.send(("start",))
        return process, parent

    try:
        first, first_pipe = start(False, True)
        assert _receive(first_pipe) == ("running", False)
        second, second_pipe = start(True, False)
        assert _receive(second_pipe) == ("lock_attempt",)
        assert not second_pipe.poll(0.1)
        first_pipe.send(("complete",))
        assert _receive(first_pipe) == ("published", "complete\n")
        assert marker.read_text() == "complete\n"
        assert not second_pipe.poll(0.1), "lock released before marker publication"
        first_pipe.send(("return",))
        assert _receive(first_pipe) == ("done",)
        first.join(8)
        assert first.exitcode == 0
        assert _receive(second_pipe) == ("lock_acquired",)
        assert _receive(second_pipe) == ("running", False)
        second.kill()
        second.join(8)
        assert not second.is_alive()
        assert not marker.exists(), "interrupted transfer left a success marker"
        third, third_pipe = start(False, False)
        assert _receive(third_pipe) == ("running", False)
        third_pipe.send(("complete",))
        assert _receive(third_pipe) == ("done",)
        third.join(8)
        assert third.exitcode == 0
        assert marker.read_text() == "complete\n"
    finally:
        for process, pipe in children:
            if process.is_alive():
                process.kill()
            process.join(8)
            pipe.close()


@pytest.mark.skipif(os.name != "posix", reason="sync requires real POSIX flock")
@pytest.mark.parametrize("delete", [False, True])
@pytest.mark.parametrize("source_has_lock", [False, True])
def test_real_local_rsync_payload_cannot_replace_coordination_lock(
    tmp_path: Path,
    delete: bool,
    source_has_lock: bool,
) -> None:
    if shutil.which("rsync") is None:
        pytest.skip("local rsync executable unavailable")
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "data").write_bytes(b"synthetic-content")
    if source_has_lock:
        (source / ".gunz-sync.lock").write_bytes(b"synthetic-source-control-file")
    lock_path = target / ".gunz-sync.lock"
    lock_path.write_bytes(b"synthetic-coordination-lock")
    inode = lock_path.stat().st_ino
    rsync_mirror(source, target, timeout=5, delete=delete, extra_args=("--include=*",))
    assert lock_path.stat().st_ino == inode
    assert lock_path.read_bytes() == b"synthetic-coordination-lock"
    assert (target / "data").read_bytes() == b"synthetic-content"


@pytest.mark.parametrize("marker_name", ["complete[1]", "complete*", "complete?"])
def test_real_local_rsync_treats_reserved_marker_pattern_characters_literally(
    tmp_path: Path,
    marker_name: str,
) -> None:
    if shutil.which("rsync") is None:
        pytest.skip("local rsync executable unavailable")
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    (source / marker_name).write_bytes(b"synthetic-source-marker")
    (source / "completeX").write_bytes(b"ordinary-content")
    import gunz_utils.sync as module

    original_write = module.atomic_write
    publications = []

    def verify_before_publication(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        assert not (target / marker_name).exists(), (
            "source published the reserved marker"
        )
        publications.append(True)
        return original_write(*args, **kwargs)

    with patch.object(module, "atomic_write", verify_before_publication):
        result = rsync_mirror(
            source,
            target,
            timeout=5,
            completion_marker=marker_name,
            extra_args=("--include=*",),
        )
    assert publications == [True]
    assert result.completion_marker is not None
    assert result.completion_marker.read_text() == "complete\n"
    assert (target / "completeX").read_bytes() == b"ordinary-content"
    assert any("H /complete" in arg for arg in result.command.args)


@pytest.mark.skipif(os.name != "posix", reason="sync requires real POSIX flock")
@pytest.mark.parametrize(
    "option", ["--include=!", "--exclude=!", "--include-from", "--exclude-from", "-F"]
)
def test_admitted_rule_sources_do_not_override_global_reserved_lock_rules(
    tmp_path: Path,
    option: str,
) -> None:
    if shutil.which("rsync") is None:
        pytest.skip("local rsync executable unavailable")
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / ".gunz-sync.lock").write_bytes(b"synthetic-source-control-file")
    (source / "data").write_bytes(b"synthetic-content")
    (source / ".rsync-filter").write_text("!\n+ *\n")
    reset_rules = tmp_path / "synthetic-reset-rules"
    reset_rules.write_text("!\n")
    extra = (option, str(reset_rules)) if option.endswith("-from") else (option,)
    lock_path = target / ".gunz-sync.lock"
    lock_path.write_bytes(b"synthetic-coordination-lock")
    inode = lock_path.stat().st_ino
    if option != "-F":
        with pytest.raises(ValueError, match="unsafe rsync options"):
            rsync_mirror(
                source,
                target,
                timeout=5,
                delete=True,
                extra_args=(*extra, "--include=*"),
            )
        assert not (target / "data").exists()
    else:
        rsync_mirror(
            source, target, timeout=5, delete=True, extra_args=(*extra, "--include=*")
        )
        assert (target / "data").read_bytes() == b"synthetic-content"
    assert lock_path.stat().st_ino == inode
    assert lock_path.read_bytes() == b"synthetic-coordination-lock"


@pytest.mark.parametrize(
    "extra",
    [
        ("--include", "!"),
        ("--exclude", "!"),
        ("--include-f=synthetic-rules",),
        ("--exclude-f=synthetic-rules",),
    ],
)
def test_split_resets_and_abbreviated_external_rule_sources_reject_before_side_effects(
    tmp_path: Path,
    extra: tuple[str, ...],
) -> None:
    target = tmp_path / "target"
    with pytest.raises(ValueError, match="unsafe rsync options"):
        rsync_mirror("synthetic-source", target, extra_args=extra)
    assert not target.exists()


@pytest.mark.parametrize(
    "extra",
    [
        ("-af", "!", "--include=*"),
        ("-avf", "!", "--include=*"),
        ("-ae", "synthetic-shell"),
        ("-avM", "synthetic-remote-option"),
        ("-Tsynthetic-dir",),
        ("-avT", "synthetic-dir"),
    ],
)
def test_forbidden_clustered_flags_preserve_lock_and_reject_before_command(
    tmp_path: Path,
    extra: tuple[str, ...],
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / ".gunz-sync.lock").write_bytes(b"synthetic-source-control-file")
    lock_path = target / ".gunz-sync.lock"
    lock_path.write_bytes(b"synthetic-coordination-lock")
    marker = target / ".gunz-sync-complete"
    marker.write_bytes(b"synthetic-old-marker")
    inode = lock_path.stat().st_ino
    with patch("gunz_utils.sync.run_command") as command:
        with pytest.raises(ValueError, match="unsafe rsync options"):
            rsync_mirror(source, target, timeout=3, extra_args=extra)
        command.assert_not_called()
    assert lock_path.stat().st_ino == inode
    assert lock_path.read_bytes() == b"synthetic-coordination-lock"
    assert marker.read_bytes() == b"synthetic-old-marker"


@pytest.mark.parametrize("option", ["-av", "-F", "-aF", "-B1M", "-@1"])
def test_short_cluster_parser_preserves_flags_and_attached_argument_payloads(
    option: str,
) -> None:
    assert not _unsafe_rsync_extra_argument(option)


@pytest.mark.skipif(os.name != "posix", reason="sync requires real POSIX flock")
@pytest.mark.parametrize("option", ["-av", "-aF", "-aB1024"])
def test_real_local_rsync_ordinary_short_clusters_preserve_lock(
    tmp_path: Path,
    option: str,
) -> None:
    if shutil.which("rsync") is None:
        pytest.skip("local rsync executable unavailable")
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "data").write_bytes(b"synthetic-content")
    (source / ".gunz-sync.lock").write_bytes(b"synthetic-source-control-file")
    lock_path = target / ".gunz-sync.lock"
    lock_path.write_bytes(b"synthetic-coordination-lock")
    inode = lock_path.stat().st_ino
    rsync_mirror(source, target, timeout=3, extra_args=(option,))
    assert lock_path.stat().st_ino == inode
    assert lock_path.read_bytes() == b"synthetic-coordination-lock"
    assert (target / "data").read_bytes() == b"synthetic-content"
