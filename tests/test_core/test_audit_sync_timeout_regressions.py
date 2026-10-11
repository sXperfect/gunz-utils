"""Invalid sync configuration preserves filesystem coordination evidence."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import Mock

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
from gunz_utils.sync import rsync_mirror


@pytest.mark.parametrize("timeout", [math.nan, math.inf, -math.inf, True, False, -1, 0])
@pytest.mark.parametrize("existing", [True, False])
def test_invalid_timeout_is_rejected_before_filesystem_or_command_actions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    timeout: float,
    existing: bool,
) -> None:
    destination = tmp_path / "destination"
    marker = destination / ".gunz-sync-complete"
    before = None
    if existing:
        destination.mkdir()
        marker.write_bytes(b"synthetic prior successful sync\n")
        before = marker.stat()
    which = Mock(side_effect=AssertionError("executable lookup before validation"))
    execute = Mock(side_effect=AssertionError("command before validation"))
    monkeypatch.setattr("gunz_utils.sync.shutil.which", which)
    monkeypatch.setattr("gunz_utils.sync.run_command", execute)
    with pytest.raises(ValueError, match="finite positive"):
        rsync_mirror(tmp_path / "source", destination, timeout=timeout)
    which.assert_not_called()
    execute.assert_not_called()
    assert destination.exists() is existing
    if before is not None:
        assert marker.read_bytes() == b"synthetic prior successful sync\n"
        assert marker.stat() == before
        assert set(destination.iterdir()) == {marker}


def test_valid_timeout_keeps_marker_success_and_failure_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    marker = destination / ".gunz-sync-complete"
    monkeypatch.setattr(
        "gunz_utils.sync.shutil.which", lambda _name: "/synthetic/rsync"
    )

    def execute(
        args: list[str],
        **kwargs: object,
    ) -> CommandResult:
        assert not marker.exists()
        assert kwargs["timeout"] == 1
        assert "--dry-run" in args
        return CommandResult(tuple(args), 0, "", "", 0)

    monkeypatch.setattr("gunz_utils.sync.run_command", execute)
    marker.write_text("old completion")
    rsync_mirror(
        tmp_path / "source",
        destination,
        timeout=1,
        lock=False,
        extra_args=["--dry-run"],
    )
    assert marker.read_text() == "complete\n"
    failure = RuntimeError("synthetic sync failed")

    def fail(
        args: list[str],
        **kwargs: object,
    ) -> CommandResult:
        assert not marker.exists()
        raise failure

    monkeypatch.setattr("gunz_utils.sync.run_command", fail)
    with pytest.raises(RuntimeError) as observed:
        rsync_mirror(tmp_path / "source", destination, timeout=1, lock=False)
    assert observed.value is failure
    assert not marker.exists()
