"""Perpetual security & concurrency audit - PHASE 16 (round-3) regression tests.

Round-3 re-audit of network, serialization, redaction, and provenance_graph
(the deepest deferred/NEW issues two prior passes missed). Tests are written to
FAIL ("red") against the current source (base a898068, which already contains
the phase 1-15 fixes) and must pass only after the corresponding production fix
lands. Production code is intentionally not modified.

Findings covered here (NEW, not previously flagged):
1. ``_is_non_public_address`` (network.py:184-191) does not treat the shared
   CGNAT range ``100.64.0.0/10`` (RFC 6598) as non-public. For addresses in that
   range, ``ipaddress`` reports ``is_private=False``, ``is_global=False`` and
   ``is_reserved=False``, and the helper only checks private/loopback/link-local
   /unspecified/multicast/reserved. So ``tcp_reachable(host='100.64.0.1', ...,
   allow_private=False)`` does NOT raise and attempts a connection to a
   non-public, operator-assigned shared address - a bypass of the external-only
   probe policy (SSRF guard).
2. ``redact`` (redaction.py:123) concatenates a fixed four-character mask on top
   of the shown prefix and suffix without trimming, so the documented
   "same length preserved" invariant (redaction.py:99) is violated and a middle
   character is silently dropped whenever ``len(value) != 2 * show_chars + 4``.
   For example ``redact("hunter2")`` returns ``"hu****r2"`` (8 chars) instead of
   a length-preserving ``"hu***r2"`` (7 chars), and ``redact("abcdefghi",
   show_chars=2)`` drops one of the hidden middle characters.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.network import _is_non_public_address, tcp_reachable
from gunz_utils.redaction import redact

# -----------------------------------------------------------------------------
# network.py - shared CGNAT range 100.64.0.0/10 is not treated as non-public
# -----------------------------------------------------------------------------


def test_is_non_public_address_rejects_cgnat_shared_range() -> None:
    """The shared CGNAT range 100.64.0.0/10 (RFC 6598) is not public internet.

    ``_is_non_public_address`` (network.py:184-191) relies on
    ``is_private``/``is_global``/``is_reserved``, all of which are ``False`` for
    100.64.0.0/10, so this returns ``False`` today and would let an external-only
    probe connect to a non-public, operator-assigned CGNAT address.
    """
    assert _is_non_public_address("100.64.0.1") is True


def test_tcp_reachable_allow_private_false_rejects_cgnat() -> None:
    """``allow_private=False`` must reject a shared CGNAT address with an error.

    With ``allow_private=False`` the policy is "external-only"; a 100.64.0.0/10
    address is not globally routable public internet, so the probe must raise
    ``ValueError`` rather than attempt the connection.
    """
    with pytest.raises(ValueError):
        tcp_reachable("100.64.0.1", 443, allow_private=False)


# -----------------------------------------------------------------------------
# redaction.py - redact() does not preserve the documented output length
# -----------------------------------------------------------------------------


def test_redact_masked_value_preserves_length() -> None:
    """``redact`` must preserve the input length (documented at redaction.py:99).

    ``redact("hunter2")`` (len 7, ``show_chars=2``) currently returns
    ``"hu****r2"`` (len 8) because the fixed four-char mask is added on top of
    the prefix and suffix instead of being sized to the hidden middle.
    """
    assert len(redact("hunter2")) == 7


def test_redact_preserves_all_hidden_middle_characters() -> None:
    """``redact`` must not silently drop characters from the hidden middle.

    ``redact("abcdefghi", show_chars=2)`` hides five middle characters and must
    yield a string of length 9 (prefix ``ab`` + five masked + suffix ``hi``).
    The fixed four-char mask currently drops one hidden character.
    """
    assert len(redact("abcdefghi", show_chars=2)) == 9


# -----------------------------------------------------------------------------
# Sanity green - reference behavior that must keep working
# -----------------------------------------------------------------------------


def test_is_non_public_address_public_and_private_reference() -> None:
    """Sanity green: public addresses stay public, RFC 1918 stays non-public."""
    assert _is_non_public_address("8.8.8.8") is False
    assert _is_non_public_address("10.0.0.1") is True
    assert _is_non_public_address("fe80::1") is True


def test_redact_short_string_fully_masked() -> None:
    """Sanity green: strings at/below the reveal threshold are fully masked."""
    assert redact("hi") == "****"
    assert redact("hunter2", show_chars=4) == "****"
    assert redact(12345) == 12345
