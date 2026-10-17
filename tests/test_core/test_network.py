"""Tests for shared network URI and TCP helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import socket
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

from gunz_utils.network import build_network_uri, tcp_reachable


def test_build_network_uri_encodes_user_info_path_and_query() -> None:
    uri = build_network_uri(
        "HTTPS",
        "example.com",
        port=8443,
        username="user@example.com",
        password="p a:ss",
        path="api/v1 items",
        query={"limit": 5, "tag": ["a", "b"]},
    )

    assert uri == (
        "https://user%40example.com:p%20a%3Ass@example.com:8443/"
        "api/v1%20items?limit=5&tag=a&tag=b"
    )


def test_build_network_uri_brackets_bare_ipv6() -> None:
    uri = build_network_uri(
        "http",
        "2001:db8::1",
        port=8080,
    )

    assert uri == "http://[2001:db8::1]:8080"


def test_build_network_uri_validates_configuration() -> None:
    with pytest.raises(ValueError, match="scheme"):
        build_network_uri("not a scheme", "example.com")

    with pytest.raises(ValueError, match="host"):
        build_network_uri("http", "")

    with pytest.raises(ValueError, match="port"):
        build_network_uri("http", "example.com", port=0)

    with pytest.raises(ValueError, match="password requires"):
        build_network_uri(
            "http",
            "example.com",
            password="secret",
        )


def test_tcp_reachable_reports_listening_local_socket() -> None:
    listener = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    host, port = listener.getsockname()
    try:
        assert tcp_reachable(
            host,
            port,
            timeout=0.5,
        )
    finally:
        listener.close()


def test_tcp_reachable_validates_arguments() -> None:
    with pytest.raises(ValueError, match="host"):
        tcp_reachable("", 80)

    with pytest.raises(ValueError, match="port"):
        tcp_reachable("localhost", 65536)

    with pytest.raises(ValueError, match="timeout"):
        tcp_reachable("localhost", 80, timeout=0)



def test_build_network_uri_rejects_authority_injection_and_bad_brackets() -> None:
    with pytest.raises(ValueError, match="delimiters"):
        build_network_uri(
            "https",
            "example.com@evil.test",
        )

    with pytest.raises(ValueError, match="whitespace"):
        build_network_uri(
            "https",
            "exa mple.com",
        )

    with pytest.raises(ValueError, match="brackets"):
        build_network_uri(
            "https",
            "[2001:db8::1",
        )


def test_build_network_uri_rejects_boolean_port_and_empty_username() -> None:
    with pytest.raises(ValueError, match="port"):
        build_network_uri(
            "https",
            "example.com",
            port=True,
        )

    with pytest.raises(ValueError, match="username"):
        build_network_uri(
            "https",
            "example.com",
            username="",
        )


def test_tcp_reachable_rejects_boolean_port_and_timeout() -> None:
    with pytest.raises(ValueError, match="port"):
        tcp_reachable(
            "localhost",
            True,
        )

    with pytest.raises(ValueError, match="timeout"):
        tcp_reachable(
            "localhost",
            80,
            timeout=True,
        )



def test_build_network_uri_rejects_malformed_ipv6_hosts() -> None:
    with pytest.raises(ValueError, match="valid IPv6"):
        build_network_uri(
            "https",
            "[not-ipv6]",
        )

    with pytest.raises(ValueError, match="valid IPv6"):
        build_network_uri(
            "https",
            "host:not-ipv6",
        )


def test_build_network_uri_idna_normalizes_dns_host() -> None:
    uri = build_network_uri(
        "https",
        "münich.example",
    )

    assert uri == "https://xn--mnich-kva.example"


def test_build_network_uri_rejects_backslash_and_control_characters() -> None:
    with pytest.raises(ValueError, match="authority characters"):
        build_network_uri("https", r"example.com\evil.test")

    with pytest.raises(ValueError, match="authority characters"):
        build_network_uri("https", "example.com\x7fevil.test")


def test_tcp_reachable_blocks_literal_private_address_before_connect() -> None:
    with patch("gunz_utils.network.socket.create_connection") as connect:
        with pytest.raises(ValueError, match="non-public"):
            tcp_reachable(
                "127.0.0.1",
                80,
                allow_private=False,
            )
    connect.assert_not_called()


def test_tcp_reachable_blocks_hostname_resolving_to_private_address() -> None:
    address_info = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("10.0.0.5", 443),
        )
    ]
    with (
        patch(
            "gunz_utils.network.socket.getaddrinfo",
            return_value=address_info,
        ),
        patch("gunz_utils.network.socket.create_connection") as connect,
    ):
        with pytest.raises(ValueError, match="non-public"):
            tcp_reachable(
                "internal.example",
                443,
                allow_private=False,
            )
    connect.assert_not_called()


def test_tcp_reachable_connects_to_validated_public_numeric_address() -> None:
    address_info = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("93.184.216.34", 443),
        )
    ]
    with (
        patch(
            "gunz_utils.network.socket.getaddrinfo",
            return_value=address_info,
        ),
        patch("gunz_utils.network.socket.create_connection") as connect,
    ):
        assert tcp_reachable(
            "example.test",
            443,
            allow_private=False,
        )

    assert connect.call_count == 1
    call_target, call_kwargs = connect.call_args
    assert call_target == (("93.184.216.34", 443),)
    #? The timeout is bounded by the deadline budget (approx 5.0s).
    assert math.isclose(call_kwargs["timeout"], 5.0, abs_tol=0.1)


def test_tcp_reachable_cumulative_timeout_across_addresses() -> None:
    address_info = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("93.184.216.34", 443),
        ),
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("93.184.216.35", 443),
        ),
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("93.184.216.36", 443),
        ),
    ]

    current_time = 100.0

    def mock_monotonic() -> float:
        return current_time

    observed_timeouts: list[float] = []

    def mock_create_connection(
        target: tuple[str, int],
        *,
        timeout: float,
    ) -> None:
        nonlocal current_time
        observed_timeouts.append(timeout)
        #? Advance simulated clock by 3.0 seconds per attempt
        current_time += 3.0
        raise OSError("connection timed out")

    with (
        patch(
            "gunz_utils.network.socket.getaddrinfo",
            return_value=address_info,
        ),
        patch(
            "gunz_utils.network.time.monotonic",
            side_effect=mock_monotonic,
        ),
        patch(
            "gunz_utils.network.socket.create_connection",
            side_effect=mock_create_connection,
        ),
    ):
        result = tcp_reachable(
            "example.test",
            443,
            timeout=5.0,
            allow_private=False,
        )

    #? Total budget is 5.0s. First attempt takes 3.0s, leaving 2.0s for second attempt.
    #? Second attempt takes 3.0s, exceeding budget; third attempt is not executed.
    assert result is False
    assert len(observed_timeouts) == 2
    assert math.isclose(observed_timeouts[0], 5.0, abs_tol=0.01)
    assert math.isclose(observed_timeouts[1], 2.0, abs_tol=0.01)


def test_tcp_reachable_validates_allow_private_type() -> None:
    with pytest.raises(TypeError, match="allow_private"):
        tcp_reachable(
            "example.test",
            443,
            allow_private="no",
        )
