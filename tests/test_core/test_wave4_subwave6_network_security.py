"""Tests for Wave 4 Sub-Wave 6: Network, Security & Notebooks (#66–#77)."""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from gunz_utils.network import (
    ParsedURI,
    is_loopback_host,
    is_public_ip,
    parse_network_uri,
    sanitize_uri,
)
from gunz_utils.notebook import is_colab, is_notebook
from gunz_utils.security import (
    constant_time_equals,
    is_dos_device_name,
    sanitize_path_segment,
    validate_token_entropy,
    verify_no_symlink_escape,
)


# =============================================================================
# #66–#70: Network helpers
# =============================================================================

def test_parse_network_uri():
    parsed = parse_network_uri("https://admin:secret@api.example.com:8443/v1/users?limit=10#top")
    assert isinstance(parsed, ParsedURI)
    assert parsed.scheme == "https"
    assert parsed.host == "api.example.com"
    assert parsed.port == 8443
    assert parsed.path == "/v1/users"
    assert parsed.query == "limit=10"
    assert parsed.fragment == "top"
    assert parsed.username == "admin"

    with pytest.raises(ValueError, match="invalid URI scheme"):
        parse_network_uri("123bad://host.com")
    with pytest.raises(ValueError, match="valid host"):
        parse_network_uri("https://")


def test_is_public_ip():
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("1.1.1.1") is True
    assert is_public_ip("192.168.1.1") is False   # Private
    assert is_public_ip("10.0.0.1") is False      # Private
    assert is_public_ip("127.0.0.1") is False     # Loopback
    assert is_public_ip("169.254.1.1") is False   # Link-local
    assert is_public_ip("::1") is False           # Loopback IPv6
    assert is_public_ip("fe80::1") is False       # Link-local IPv6
    assert is_public_ip("invalid-ip") is False


def test_is_loopback_host():
    assert is_loopback_host("localhost") is True
    assert is_loopback_host("LOCALHOST") is True
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("127.100.200.1") is True
    assert is_loopback_host("::1") is True
    assert is_loopback_host("[::1]") is True
    assert is_loopback_host("example.com") is False
    assert is_loopback_host("8.8.8.8") is False


def test_sanitize_uri():
    redacted = sanitize_uri("postgres://admin:supersecret@db.internal:5432/main?ssl=true")
    assert redacted == "postgres://admin:***@db.internal:5432/main?ssl=true"
    assert "supersecret" not in redacted

    clean = sanitize_uri("https://example.com/api")
    assert clean == "https://example.com/api"


# =============================================================================
# #71–#75: Security helpers
# =============================================================================

def test_sanitize_path_segment():
    assert sanitize_path_segment("normal_file.txt") == "normal_file.txt"
    assert sanitize_path_segment("../../etc/passwd") == "_etc_passwd"
    assert sanitize_path_segment("..") == "_"
    assert sanitize_path_segment(".") == "_"

    with pytest.raises(ValueError, match="null byte"):
        sanitize_path_segment("file\0name")


def test_validate_token_entropy():
    # Low entropy (repeating characters)
    assert validate_token_entropy("aaaaaaaabbbbbbbb", min_entropy_bits=64.0) is False

    # High entropy (random base64/hex token)
    high_entropy = "d3FhMmIxYzRkNWU2ZzdoOWkwayFsQG0jbnBv"
    assert validate_token_entropy(high_entropy, min_entropy_bits=64.0) is True

    assert validate_token_entropy("", min_entropy_bits=64.0) is False


def test_constant_time_equals():
    assert constant_time_equals("secret_token_123", "secret_token_123") is True
    assert constant_time_equals("secret_token_123", "wrong_token_456") is False
    assert constant_time_equals(b"binary\x00data", b"binary\x00data") is True
    assert constant_time_equals(b"binary\x00data", b"binary\x01data") is False


def test_is_dos_device_name():
    assert is_dos_device_name("CON") is True
    assert is_dos_device_name("con.txt") is True
    assert is_dos_device_name("prn") is True
    assert is_dos_device_name("aux.dat") is True
    assert is_dos_device_name("nul") is True
    assert is_dos_device_name("COM1") is True
    assert is_dos_device_name("LPT3") is True
    assert is_dos_device_name("normal_file.txt") is False


def test_verify_no_symlink_escape():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        sub = base / "subdir"
        sub.mkdir()
        file = sub / "file.txt"
        file.touch()

        assert verify_no_symlink_escape(file, base) is True

        # Escaped path
        outside = Path(tmpdir).parent / "outside.txt"
        assert verify_no_symlink_escape(outside, sub) is False


# =============================================================================
# #76–#77: Notebook detection & Parity
# =============================================================================

def test_notebook_detection():
    # Under regular test runner, should be False
    assert isinstance(is_notebook(), bool)
    assert isinstance(is_colab(), bool)
    assert is_colab() is False
