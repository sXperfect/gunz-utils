"""Tests for shared network URI and TCP helpers."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

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

    connect.assert_called_once_with(
        ("93.184.216.34", 443),
        timeout=5.0,
    )


def test_tcp_reachable_validates_allow_private_type() -> None:
    with pytest.raises(TypeError, match="allow_private"):
        tcp_reachable(
            "example.test",
            443,
            allow_private="no",
        )
