"""Perpetual security & concurrency audit - PHASE 19 (round-3) regression tests.

Round-3 re-audit of sync, security, content_store, and provenance (the deepest
deferred/NEW issues two prior passes missed). Tests are written to FAIL ("red")
against the current source (base 450d8fa, which already contains the phase 1-18
fixes) and must pass only after the corresponding production fix lands.
Production code is intentionally not modified.

Findings covered here (NEW, not previously flagged):

1. ``_redact_environment_value`` (provenance.py:74) only redacts URL user-info
   credentials when they sit in the ``netloc`` component AND ``parsed.scheme``
   is truthy (``parsed.scheme and "@" in parsed.netloc``). Any URL-like value
   whose ``user:pass@`` authority is NOT in ``netloc`` is emitted verbatim into
   the provenance manifest. This leaks passwords for scheme-relative URLs
   (``//user:pass@host``), scheme-less URLs (``user:pass@host``), and
   single-colon schemes with the authority in the path
   (``postgres:user:pass@host``) - all legitimate URL forms. An allowlisted
   environment variable carrying such a value therefore leaks its credential
   into the captured manifest, defeating the module's credential-redaction
   guarantee.

2. ``sanitize_filename`` (security.py:93) "collapse multiple replacements"
   (security.py:166-169) runs ``pattern.sub(replacement, filename)`` over the
   WHOLE filename, collapsing every consecutive run of the replacement
   character - including runs that were already valid in the input and were
   never produced by substitution. Because the default replacement ``"_"`` is a
   legal filename character, a perfectly valid name such as ``"foo__bar"`` is
   silently rewritten to ``"foo_bar"``. Two distinct valid inputs then map to
   the same sanitized output (``sanitize_filename("foo__bar")`` ==
   ``sanitize_filename("foo_bar")``), a name collision that can cause a later
   write to clobber an unrelated file. The defect is worse for a non-default
   alphanumeric replacement: ``sanitize_filename("hello", "l")`` returns
   ``"helo"``, dropping a genuine character.
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

from gunz_utils.provenance import _redact_environment_value
from gunz_utils.security import sanitize_filename

# -----------------------------------------------------------------------------
# provenance.py - _redact_environment_value leaks URL user-info passwords when
# the authority is not in the netloc component
# -----------------------------------------------------------------------------


def test_redact_environment_value_scheme_relative_url_password() -> None:
    """RED: scheme-relative authority must have its password redacted."""
    redacted = _redact_environment_value("DB_HOST", "//user:supersecretpw@host")
    assert "supersecretpw" not in redacted
    assert "****" in redacted


def test_redact_environment_value_scheme_less_url_password() -> None:
    """RED: scheme-less authority must have its password redacted."""
    redacted = _redact_environment_value("DB_HOST", "user:supersecretpw@host")
    assert "supersecretpw" not in redacted
    assert "****" in redacted


def test_redact_environment_value_single_colon_scheme_password() -> None:
    """RED: a single-colon scheme (e.g. postgres:user:pass@host) must redact."""
    redacted = _redact_environment_value("DB_HOST", "postgres:user:supersecretpw@host")
    assert "supersecretpw" not in redacted
    assert "****" in redacted


def test_redact_environment_value_netloc_password_still_redacted() -> None:
    """Sanity green: an ordinary netloc authority is already redacted."""
    redacted = _redact_environment_value("DB_HOST", "postgres://user:supersecretpw@host")
    assert "supersecretpw" not in redacted
    assert "****" in redacted


# -----------------------------------------------------------------------------
# security.py - sanitize_filename collapses valid characters into the
# replacement, destroying content and causing name collisions
# -----------------------------------------------------------------------------


def test_sanitize_filename_preserves_valid_double_separator() -> None:
    """RED: valid double underscore must be preserved, not collapsed."""
    assert sanitize_filename("foo__bar") == "foo__bar"


def test_sanitize_filename_does_not_collide_distinct_names() -> None:
    """RED: distinct valid inputs must not map to the same sanitized name."""
    assert sanitize_filename("foo__bar") != sanitize_filename("foo_bar")


def test_sanitize_filename_alpha_replacement_preserves_chars() -> None:
    """RED: an alphanumeric replacement must not delete genuine characters."""
    assert sanitize_filename("hello", "l") == "hello"


def test_sanitize_filename_single_separator_unchanged() -> None:
    """Sanity green: a single underscore is left untouched."""
    assert sanitize_filename("foo_bar") == "foo_bar"


def test_sanitize_filename_single_invalid_char_still_replaced() -> None:
    """Sanity green: an invalid char is still replaced with the default."""
    assert sanitize_filename("a!b") == "a_b"
