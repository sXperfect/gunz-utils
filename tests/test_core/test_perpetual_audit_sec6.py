"""Perpetual security & concurrency audit - PHASE 6 regression tests.

Each test exposes a concrete input-validation, resource-bound, or
error-reporting defect in the audited modules (network, serialization,
redaction, security, leases). Tests are written to FAIL ("red") against the
current source and must pass only after the corresponding production fix
lands. Production code is intentionally not modified.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import json

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.network import build_network_uri, tcp_reachable
from gunz_utils.serialization import json_loads


# -----------------------------------------------------------------------------
# serialization.py - json_loads does not bound nesting depth
# -----------------------------------------------------------------------------


def test_json_loads_bounds_deeply_nested_input() -> None:
    """``json_loads`` must reject pathological nesting with ``JSONDecodeError``.

    The encode side ``to_jsonable`` bounds recursion depth (``_max_depth=100``)
    and raises ``ValueError`` on excess, but the decode side ``json_loads`` is a
    bare ``json.loads(value)`` with no depth bound. Pathologically nested JSON
    therefore surfaces an uncontrolled ``RecursionError`` (a ``RuntimeError``)
    instead of the documented decoder error ``JSONDecodeError`` (a
    ``ValueError``). Callers catching ``JSONDecodeError`` (the conventional
    contract for parsing untrusted JSON) will not catch ``RecursionError``.
    """
    deeply_nested = "[" * 100_000 + "]" * 100_000
    with pytest.raises(json.JSONDecodeError):
        json_loads(deeply_nested)


def test_json_loads_bounds_deeply_nested_bytes_input() -> None:
    """``json_loads`` bytes/bytearray input must also raise ``JSONDecodeError``.

    The public contract accepts ``str | bytes | bytearray``. For excessive
    nesting, the depth-bounding fix decodes bytes to text for the scan but
    then constructs ``json.JSONDecodeError(msg, value, position)`` with the
    original ``bytes`` value. ``JSONDecodeError.__init__`` calls
    ``doc.count('\\n', 0, pos)`` on that bytes doc, which raises a
    ``TypeError`` ("argument should be integer or bytes-like object, not
    'str'") instead of the documented ``JSONDecodeError``. The bytes path must
    surface the same controlled decoder error as the str path.
    """
    deeply_nested = ("[" * 100_000 + "]" * 100_000).encode("utf-8")
    with pytest.raises(json.JSONDecodeError):
        json_loads(deeply_nested)


# -----------------------------------------------------------------------------
# network.py - tcp_reachable accepts a timeout that crashes the socket layer
# -----------------------------------------------------------------------------


def test_tcp_reachable_rejects_oversized_timeout() -> None:
    """``tcp_reachable`` must reject timeouts its socket layer cannot handle.

    The timeout validation (network.py:210-216) only rejects non-finite and
    non-positive values, so a large-but-finite timeout (e.g. ``1e12`` seconds)
    passes validation. ``socket.create_connection`` then calls
    ``socket.settimeout(1e12)`` which raises ``OverflowError`` before any
    connection is attempted. A validated timeout must never crash with an
    unrelated ``OverflowError``; oversized bounds should be rejected with a
    clear ``ValueError`` during validation.
    """
    with pytest.raises(ValueError):
        tcp_reachable("1.1.1.1", 80, timeout=1e12, allow_private=False)


# -----------------------------------------------------------------------------
# network.py - build_network_uri rejects host injection (sanity green)
# -----------------------------------------------------------------------------


def test_build_network_uri_rejects_host_injection() -> None:
    """Host-injection delimiters must be rejected by ``build_network_uri``.

    Sanity green: authority validation rejects user-info/query/fragment
    delimiters, whitespace, backslashes, and port-embedded IPv6 hosts, so the
    URI builder cannot be used to smuggle a distinct authority.
    """
    for host in (
        "example.com@evil.com",
        "evil.com#fragment",
        "exa mple.com",
        "example.com\\evil",
        "[::1]:8080",
    ):
        with pytest.raises(ValueError):
            build_network_uri("http", host)
