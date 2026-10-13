"""Perpetual security & concurrency audit - PHASE 13 (round-2) regression tests.

Round-2 re-audit of sync, security, plugins, faults, models, and pipeline.
Tests are written to FAIL ("red") against the current source (base 736a07a,
which already contains the phase 1-12 fixes) and must pass only after the
corresponding production fix lands. Production code is intentionally not
modified.

Findings covered here (NEW, not previously flagged):
1. ``sanitize_filename`` (security.py:142) strips the leading/trailing
   ``replacement`` as a *character set* via ``filename.strip(replacement + ".-")``.
   When ``replacement`` is an alphanumeric character (or a multi-character
   string), valid filename boundary characters that happen to be in the
   replacement alphabet are silently removed. For example
   ``sanitize_filename("apple.txt", replacement="a")`` returns ``"pple.txt"``
   and ``sanitize_filename("a_foo_b.txt", replacement="a")`` returns
   ``"_foo_b.txt"``, corrupting legitimate basenames.
2. ``_unsafe_rsync_extra_argument`` (sync.py:92-95) rejects any option that is
   a string-prefix of a forbidden long option. Many *benign* rsync options are
   prefixes of forbidden ones (``--partial`` of ``--partial-dir``,
   ``--backup`` of ``--backup-dir``, ``--log`` of ``--log-file``, etc.), so they
   are falsely rejected as "unsafe" even though they are non-destructive.
   Notably ``--partial`` is added by ``rsync_mirror`` itself (sync.py:333) yet
   cannot be passed through ``extra_args``.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.security import sanitize_filename
from gunz_utils.sync import _unsafe_rsync_extra_argument

# -----------------------------------------------------------------------------
# security.py - sanitize_filename strips valid boundary chars as a char set
# -----------------------------------------------------------------------------


def test_sanitize_filename_preserves_leading_valid_letter() -> None:
    """A valid leading letter must not be stripped by an alphanumeric replacement.

    ``sanitize_filename`` strips ``filename.strip(replacement + ".-")``
    (security.py:142). ``str.strip`` treats its argument as a character set, so
    when ``replacement="a"`` the leading ``"a"`` of the valid basename
    ``"apple.txt"`` is removed, producing ``"pple.txt"``.
    """
    assert sanitize_filename("apple.txt", replacement="a") == "apple.txt"


def test_sanitize_filename_preserves_boundary_letter_with_replacement() -> None:
    """A valid letter adjacent to an underscore must survive sanitization."""
    assert sanitize_filename("a_foo_b.txt", replacement="a") == "a_foo_b.txt"


# -----------------------------------------------------------------------------
# sync.py - _unsafe_rsync_extra_argument false-positive on benign prefixes
# -----------------------------------------------------------------------------


def test_rsync_accepts_benign_partial_option() -> None:
    """``--partial`` (non-destructive, used internally) must not be rejected.

    ``_unsafe_rsync_extra_argument`` (sync.py:92-95) rejects any option that is
    a string-prefix of a forbidden long option. ``--partial`` is a prefix of the
    forbidden ``--partial-dir``, so it is wrongly classified as unsafe even
    though ``rsync_mirror`` itself passes ``--partial`` by default (sync.py:333).
    """
    assert _unsafe_rsync_extra_argument("--partial") is False


def test_rsync_accepts_benign_backup_option() -> None:
    """``--backup`` (non-destructive) must not be rejected as a prefix match."""
    assert _unsafe_rsync_extra_argument("--backup") is False


# -----------------------------------------------------------------------------
# Sanity green - genuinely unsafe options still rejected, default behavior intact
# -----------------------------------------------------------------------------


def test_rsync_still_rejects_unsafe_delete_option() -> None:
    """Sanity green: truly destructive/execution-affecting options stay rejected."""
    assert _unsafe_rsync_extra_argument("--delete") is True
    assert _unsafe_rsync_extra_argument("--partial-dir") is True
    assert _unsafe_rsync_extra_argument("-e") is True


def test_rsync_accepts_benign_archive_and_compress() -> None:
    """Sanity green: unrelated benign options are still accepted."""
    assert _unsafe_rsync_extra_argument("--archive") is False
    assert _unsafe_rsync_extra_argument("--compress") is False


def test_sanitize_filename_default_behaviour_unchanged() -> None:
    """Sanity green: default underscore replacement and normal names unchanged."""
    assert sanitize_filename("my_file.txt") == "my_file.txt"
    assert sanitize_filename("a-b.txt") == "a-b.txt"


# -----------------------------------------------------------------------------
# REGRESSION - worker-a's sanitize fix must not reintroduce leading dashes
# -----------------------------------------------------------------------------


def test_sanitize_filename_no_leading_dash_after_interleaved_boundary() -> None:
    """Interleaved boundary chars must not expose a leading dash.

    The boundary stripper strips leading ``.``/``-`` and then replacement
    units separately. A name like ``_-foo_`` loses its leading ``_`` but keeps
    the now-exposed ``-``, yielding option-shaped ``-foo``. This regresses
    VULN-2026-001 (leading dashes parsed as CLI options).
    """
    assert sanitize_filename("_-foo_") == "foo"


def test_sanitize_filename_strips_all_interleaved_boundary_units() -> None:
    """A dash-only-leading name must still be fully normalized."""
    assert sanitize_filename("_-_-x") == "x"


# -----------------------------------------------------------------------------
# REGRESSION - worker-a's rsync fix must not allow forbidden abbreviations
# -----------------------------------------------------------------------------


def test_rsync_rejects_forbidden_abbreviation_temp() -> None:
    """``--temp`` abbreviates the forbidden ``--temp-dir`` and must stay blocked."""
    assert _unsafe_rsync_extra_argument("--temp") is True


def test_rsync_rejects_forbidden_abbreviation_write() -> None:
    """``--write`` abbreviates the forbidden ``--write-batch`` and must stay blocked."""
    assert _unsafe_rsync_extra_argument("--write") is True
