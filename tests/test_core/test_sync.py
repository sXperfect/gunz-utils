"""Tests for shell-free rsync mirroring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gunz_utils.subprocess import CommandError, CommandResult
from gunz_utils.sync import _advisory_lock, _normalize_rsync_source, rsync_mirror


def _result(args: list[str]) -> CommandResult:
    return CommandResult(
        args=tuple(args),
        returncode=0,
        stdout="",
        stderr="",
        duration=0.1,
    )


def test_rsync_mirror_holds_lock_through_transfer_and_marker(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"
    captured: list[list[str]] = []
    events: list[str] = []

    class FakeLock:
        def __enter__(self) -> None:
            events.append("lock-enter")

        def __exit__(
            self,
            _exc_type: object,
            _exc: object,
            _traceback: object,
        ) -> None:
            events.append("lock-exit")

    def fake_run(args: list[str], **_kwargs: object) -> CommandResult:
        events.append("rsync")
        captured.append(list(args))
        return _result(list(args))

    with (
        patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"),
        patch("gunz_utils.sync._advisory_lock", return_value=FakeLock()),
        patch("gunz_utils.sync.run_command", side_effect=fake_run),
    ):
        result = rsync_mirror(
            source,
            target,
            extra_args=("--human-readable",),
        )
        events.append(
            "marker-visible"
            if result.completion_marker is not None
            and result.completion_marker.exists()
            else "marker-missing"
        )

    command = captured[0]
    assert command[0] == "rsync"
    assert "--human-readable" in command
    assert command[-3] == "--"
    assert command[-2].endswith("/source/")
    assert command[-1] == str(target.resolve())
    assert result.completion_marker is not None
    assert result.completion_marker.read_text(encoding="utf-8") == "complete\n"
    assert events[:3] == [
        "lock-enter",
        "rsync",
        "lock-exit",
    ]


def test_rsync_mirror_preserves_remote_source_syntax(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: object) -> CommandResult:
        captured.append(list(args))
        return _result(list(args))

    with (
        patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"),
        patch("gunz_utils.sync.run_command", side_effect=fake_run),
    ):
        result = rsync_mirror(
            "host:/data/input",
            tmp_path / "target",
            lock=False,
            completion_marker=None,
        )

    assert result.source == "host:/data/input/"
    assert captured[0][0] == "rsync"
    assert captured[0][-2] == "host:/data/input/"


def test_rsync_mirror_removes_marker_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    marker = target / ".gunz-sync-complete"
    marker.write_text("stale\n", encoding="utf-8")

    failure = CommandResult(
        args=("rsync",),
        returncode=1,
        stdout="",
        stderr="failed",
        duration=0.1,
    )

    with (
        patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"),
        patch(
            "gunz_utils.sync.run_command",
            side_effect=CommandError(failure),
        ),
    ):
        with pytest.raises(CommandError):
            rsync_mirror(
                tmp_path / "source",
                target,
                lock=False,
            )

    assert not marker.exists()


def test_rsync_mirror_delete_is_opt_in(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def fake_run(args: list[str], **_kwargs: object) -> CommandResult:
        captured.append(list(args))
        return _result(list(args))

    with (
        patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"),
        patch("gunz_utils.sync.run_command", side_effect=fake_run),
    ):
        rsync_mirror(
            "rsync://example/module",
            tmp_path / "target",
            lock=False,
            delete=False,
        )
        rsync_mirror(
            "rsync://example/module",
            tmp_path / "target2",
            lock=False,
            delete=True,
        )

    assert "--delete" not in captured[0]
    assert "--delete" in captured[1]


def test_rsync_mirror_validates_tools_and_marker(tmp_path: Path) -> None:
    with patch("gunz_utils.sync.shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError, match="rsync"):
            rsync_mirror(
                "source",
                tmp_path / "target",
            )

    with pytest.raises(ValueError, match="completion_marker"):
        rsync_mirror(
            "source",
            tmp_path / "target",
            completion_marker="../bad",
        )


def test_rsync_mirror_rejects_hidden_destructive_extra_args(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="destructive"):
        rsync_mirror(
            "source",
            tmp_path / "target",
            extra_args=("--delete-after",),
        )

    with pytest.raises(ValueError, match="destructive"):
        rsync_mirror(
            "source",
            tmp_path / "target",
            extra_args=("--remove-source-files",),
        )


def test_rsync_mirror_rejects_execution_affecting_extra_args(
    tmp_path: Path,
) -> None:
    for argument in (
        "-e",
        "-essh -oProxyCommand=evil",
        "--rsh=evil",
        "--rsync-path=evil",
        "--files-from=/etc/passwd",
        "--password-file=/tmp/secret",
        "--filter=merge /tmp/rules",
        "-M--copy-as=root",
        "--",
    ):
        with pytest.raises(ValueError, match="unsafe rsync"):
            rsync_mirror(
                "source",
                tmp_path / "target",
                extra_args=(argument,),
            )


def test_rsync_mirror_rejects_completion_marker_lock_collision(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="lock filename"):
        rsync_mirror(
            "source",
            tmp_path / "target",
            completion_marker=".gunz-sync.lock",
        )



def test_normalize_rsync_source_treats_windows_drive_as_local() -> None:
    assert _normalize_rsync_source(
        r"C:\data\input",
    ) == "C:/data/input/"


def test_normalize_rsync_source_keeps_shell_remote_distinct() -> None:
    assert _normalize_rsync_source(
        "build-host:/srv/data",
    ) == "build-host:/srv/data/"



def test_rsync_mirror_lock_false_does_not_require_advisory_lock(
    tmp_path: Path,
) -> None:
    def fake_run(args: list[str], **_kwargs: object) -> CommandResult:
        return _result(list(args))

    with (
        patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"),
        patch(
            "gunz_utils.sync._advisory_lock",
            side_effect=AssertionError("lock should not be used"),
        ),
        patch("gunz_utils.sync.run_command", side_effect=fake_run),
    ):
        rsync_mirror(
            "host:/data",
            tmp_path / "target",
            lock=False,
        )



def test_normalize_explicit_path_with_colon_is_local(tmp_path: Path) -> None:
    source = tmp_path / "local:name"

    normalized = _normalize_rsync_source(source)

    assert normalized == str(source.resolve()).rstrip("/") + "/"


def test_rsync_mirror_rejects_empty_target() -> None:
    with patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"):
        with pytest.raises(ValueError, match="target"):
            rsync_mirror(
                "host:/data",
                "",
                lock=False,
            )



def test_advisory_lock_rejects_symlink_path(tmp_path: Path) -> None:
    target = tmp_path / "real-lock"
    target.write_text("", encoding="utf-8")
    link = tmp_path / "lock-link"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(ValueError, match="symlink"):
        with _advisory_lock(link):
            pass
