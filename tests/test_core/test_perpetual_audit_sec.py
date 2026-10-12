"""Perpetual security & concurrency audit - PHASE 1 regression tests.

Each test in this module exposes a concrete security, input-validation, or
resource-bound defect in the audited modules. The tests are written to FAIL
("red") against the current source and must pass only after the corresponding
production fix lands. Production code is intentionally not modified here.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from pathlib import Path
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

from gunz_utils.config import env_overrides
from gunz_utils.subprocess import CommandResult
from gunz_utils.sync import _unsafe_rsync_extra_argument, rsync_mirror


def _result(
    args: list[str],
) -> CommandResult:
    return CommandResult(
        args=tuple(args),
        returncode=0,
        stdout="",
        stderr="",
        duration=0.1,
    )


# -----------------------------------------------------------------------------
# sync.py - rsync option blocklist bypass via long-option abbreviation
# -----------------------------------------------------------------------------


def test_unsafe_rsync_extra_argument_rejects_delete_abbreviation() -> None:
    """``--del`` must be rejected as unsafe.

    rsync 3.2.7 accepts ``--del`` as an unambiguous abbreviation of the
    destructive ``--delete`` option. ``_unsafe_rsync_extra_argument`` only
    rejects options that *start with* ``--delete`` (sync.py:73) and only treats
    prefixes of ``_FORBIDDEN_LONG_OPTIONS`` as forbidden (sync.py:88-94).
    Because ``--delete`` itself is not a member of ``_FORBIDDEN_LONG_OPTIONS``,
    the shorter abbreviation ``--del`` slips through both checks and is reported
    as safe even though it enables destructive deletion.
    """
    assert _unsafe_rsync_extra_argument("--del") is True
    assert _unsafe_rsync_extra_argument("--dele") is True


def test_rsync_mirror_rejects_delete_abbreviation_even_when_delete_disabled(
    tmp_path: Path,
) -> None:
    """``delete=False`` must not be bypassed through ``extra_args=("--del",)``.

    Today the mirror accepts ``--del`` and passes it to rsync, which interprets
    it as ``--delete`` and removes destination files that the caller explicitly
    declined to delete. The mirror must raise ``ValueError`` for the destructive
    abbreviation regardless of the ``delete`` flag.
    """
    source = tmp_path / "source"
    source.mkdir()

    with patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"):
        with pytest.raises(ValueError, match="unsafe rsync"):
            rsync_mirror(
                source,
                tmp_path / "target",
                delete=False,
                extra_args=("--del",),
            )


def test_rsync_mirror_still_accepts_full_delete_flag(
    tmp_path: Path,
) -> None:
    """Sanity: the explicit ``--delete`` form must remain rejected."""
    source = tmp_path / "source"
    source.mkdir()

    with patch("gunz_utils.sync.shutil.which", return_value="/usr/bin/rsync"):
        with pytest.raises(ValueError, match="unsafe rsync"):
            rsync_mirror(
                source,
                tmp_path / "target",
                extra_args=("--delete",),
            )


# -----------------------------------------------------------------------------
# config.py - case-insensitive environment key collision silently drops values
# -----------------------------------------------------------------------------


def test_env_overrides_rejects_case_insensitive_key_collision() -> None:
    """Distinct environment names that differ only by case must not silently
    overwrite each other.

    On POSIX both ``MYAPP_DEBUG`` and ``myapp_debug`` are distinct variables.
    ``env_overrides`` compares keys case-insensitively (config.py:69) but then
    slices and stores by the original key, so both collapse to the same ``debug``
    path segment. Because the conflict is only detected when the existing value
    is a *dict* (config.py:85), a scalar from one key is silently overwritten by
    the other (config.py:89), and which value wins depends on the unordered
    iteration of ``environ.items()``. The ambiguity must be rejected explicitly.
    """
    with pytest.raises(ValueError):
        env_overrides(
            {"MYAPP_DEBUG": "1", "myapp_debug": "2"},
            prefix="myapp",
        )


def test_env_overrides_single_key_still_parses() -> None:
    """A single case-normalized key must still parse normally (guard against an
    over-broad fix that rejects all environment lookups)."""
    out = env_overrides({"MYAPP_DEBUG": "1"}, prefix="myapp")
    assert out == {"debug": "1"}
