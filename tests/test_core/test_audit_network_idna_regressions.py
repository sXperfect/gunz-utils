"""Normalized hostnames must preserve URI component boundaries."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from gunz_utils.network import build_network_uri


@pytest.mark.parametrize(
    "separator", ["＠", "／", "：", "？", "＃", "％", "［", "］", "＼"]
)
def test_idna_cannot_manufacture_authority_delimiters(separator: str) -> None:
    with pytest.raises(ValueError, match="host"):
        build_network_uri("https", f"example{separator}evil.test")


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("münich.example", "xn--mnich-kva.example"),
        ("127.0.0.1", "127.0.0.1"),
        ("2001:db8::1", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
    ],
)
def test_valid_host_components_survive_uri_composition(
    host: str, expected: str
) -> None:
    parsed = urlsplit(
        build_network_uri(
            "https", host, port=8443, username="user@example", password="p:a/ss",
            path="resource", query={"key": "value"},
        )
    )
    assert parsed.hostname == expected
    assert parsed.port == 8443
    assert parsed.username == "user%40example"
    assert parsed.password == "p%3Aa%2Fss"
    assert parsed.path == "/resource"
    assert parsed.query == "key=value"
