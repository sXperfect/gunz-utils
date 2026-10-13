"""Perpetual security audit phase 30 (round 4, deepest).

Re-audit of ``config``, ``upstream_protocol``, ``resilience``, ``redaction``,
and ``network``.

Findings:

1. ``redaction.redact_dict`` leaks non-string scalar secret values that appear
   inside a collection under a secret key (redaction.py:180-191).

   In the ``secret_context`` branch, a leaf that is not a dict/list/tuple/set
   and not a ``str``/``bytes``/``bytearray``/``memoryview`` is returned
   unchanged (redaction.py:191 ``return value``).  So a secret stored as an
   ``int``/``float``/``bool`` inside a secret-keyed ``list``/``tuple`` is
   exposed verbatim, e.g. ``redact_dict({"tokens": [12345, "abc"]})`` yields
   ``{"tokens": [12345, "****"]}`` -- the numeric token is leaked.  This is
   inconsistent with the dict-key-secret path (redaction.py:203-207), which
   masks any non-string secret leaf to ``_MASK``.  Secret values in a
   secret-keyed collection must be masked regardless of their type.

2. ``config.env_overrides`` mis-parses keys when the separator starts with an
   underscore but is not a canonical underscore run (config.py:80-94).

   ``underscore_boundary = separator.startswith("_")`` (config.py:80) treats
   *any* separator that merely starts with ``_`` (e.g. ``"_X_"``) as a legacy
   underscore boundary: the key only needs a leading ``_`` after the prefix,
   not the actual separator.  So ``env_overrides({"APP_FOO": "1"}, prefix=
   "APP", separator="_X_")`` consumes ``APP_FOO`` even though that key does
   not contain the ``_X_`` separator, producing ``{"foo": "1"}``.  A key that
   does not carry the configured separator must not be consumed; the boundary
   check must honor the actual separator.

3. ``redaction.redact_dict`` validates ``show_chars`` inconsistently with
   ``redact`` (redaction.py:165-168).

   ``redact_dict`` uses only ``if show_chars < 0`` (redaction.py:168), whereas
   ``redact`` uses ``_validate_show_chars`` (redaction.py:113-121) which
   rejects booleans and non-ints with ``ValueError``.  As a result
   ``redact_dict(d, show_chars="abc")`` raises ``TypeError`` (from ``"abc" <
   0``) instead of the documented ``ValueError``, and ``show_chars=True`` is
   silently accepted when the structure has no secret keys (only erroring later
   if a secret is encountered).  ``redact_dict`` must validate ``show_chars``
   the same way ``redact`` does.
"""

import pytest

from gunz_utils.config import env_overrides
from gunz_utils.redaction import redact_dict

# ---------------------------------------------------------------------------
# Finding 1: redact_dict leaks non-string scalar secrets in secret collections
# ---------------------------------------------------------------------------


def test_redact_dict_masks_nonnumeric_scalars_in_secret_list():
    """RED: a numeric secret inside a secret-keyed list is leaked verbatim
    (``{"tokens": [12345, "abc"]}`` currently yields ``[12345, "****"]``).
    Secret values in a secret-keyed collection must be masked regardless of
    type, consistent with the dict-key-secret path.
    """
    result = redact_dict({"tokens": [12345, "abc"]})
    assert result == {"tokens": ["****", "****"]}


def test_redact_dict_masks_numeric_scalar_in_secret_tuple():
    """RED: the same leak occurs for a tuple under a secret key -- the numeric
    secret is returned unchanged instead of masked.
    """
    result = redact_dict({"tokens": (12345,)})
    assert result == {"tokens": ("****",)}


def test_redact_dict_masks_strings_and_ints_under_secret_key():
    """GREEN: a string value under a secret key is masked, and an int value
    directly under a secret key is already masked (the dict-key-secret path),
    pinning the expected masking for the collection cases above.
    """
    assert redact_dict({"api_key": "abcdef"}) == {"api_key": "ab**ef"}
    assert redact_dict({"api_key": 12345}) == {"api_key": "****"}


# ---------------------------------------------------------------------------
# Finding 2: env_overrides boundary ignores a custom underscore separator
# ---------------------------------------------------------------------------


def test_env_overrides_rejects_key_without_actual_separator():
    """RED: ``APP_FOO`` does not contain the configured ``_X_`` separator, so it
    must not be consumed as an override.  Currently the boundary check
    (``separator.startswith("_")``) treats it as a legacy underscore boundary
    and mis-parses it into ``{"foo": "1"}``.
    """
    result = env_overrides({"APP_FOO": "1"}, prefix="APP", separator="_X_")
    assert "foo" not in result
    assert result == {}


def test_env_overrides_canonical_separator_works():
    """GREEN: the canonical ``__`` separator correctly nests keys, and a key
    without the separator is correctly ignored.
    """
    assert env_overrides(
        {"APP__A__B": "1", "APP__A__C": "2"}, prefix="APP", separator="__"
    ) == {"a": {"b": "1", "c": "2"}}
    # A key with a different prefix is ignored.
    assert env_overrides({"OTHER__X": "1"}, prefix="APP", separator="__") == {}


# ---------------------------------------------------------------------------
# Finding 3: redact_dict show_chars validation is inconsistent
# ---------------------------------------------------------------------------


def test_redact_dict_rejects_non_numeric_show_chars_with_valueerror():
    """RED: ``show_chars="abc"`` currently raises ``TypeError`` (from
    ``"abc" < 0`` in the ``if show_chars < 0`` check) instead of the
    ``ValueError`` that ``redact``'s ``_validate_show_chars`` raises.  Both
    entry points must reject a non-numeric ``show_chars`` with ``ValueError``.
    """
    with pytest.raises(ValueError):
        redact_dict({"a": 1}, show_chars="abc")


def test_redact_dict_rejects_boolean_show_chars_consistently():
    """RED: ``show_chars=True`` is silently accepted when no secret key is
    present, and only errors later when a secret is actually encountered.  It
    must be rejected up front (consistently with ``redact``), regardless of
    whether a secret appears.
    """
    with pytest.raises(ValueError):
        redact_dict({"a": 1}, show_chars=True)
    with pytest.raises(ValueError):
        redact_dict({"password": "x"}, show_chars=True)


def test_redact_dict_rejects_negative_show_chars():
    """GREEN: a negative ``show_chars`` already raises ``ValueError``."""
    with pytest.raises(ValueError):
        redact_dict({"a": 1}, show_chars=-1)
