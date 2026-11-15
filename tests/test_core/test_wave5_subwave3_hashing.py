"""Tests for Wave 5 Sub-Wave 3: Advanced Hashing & Merkle Trees (#27–#39)."""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from gunz_utils.hashing import (
    MerkleTree,
    RollingHash,
    compute_file_checksum,
    fnv1a_32,
    fnv1a_64,
    hmac_sha256,
    murmurhash3_32,
    rabin_karp_hash,
    sha256_digest,
    verify_file_checksum,
)


def test_murmurhash3_32():
    h1 = murmurhash3_32("hello world")
    assert isinstance(h1, int)
    assert 0 <= h1 <= 0xFFFFFFFF
    # Deterministic
    assert murmurhash3_32("hello world") == h1
    # Seed influence
    h2 = murmurhash3_32("hello world", seed=42)
    assert h1 != h2

    # Empty string
    assert isinstance(murmurhash3_32(""), int)


def test_fnv1a_32_and_64():
    h32 = fnv1a_32("test string")
    assert isinstance(h32, int)
    assert 0 <= h32 <= 0xFFFFFFFF
    assert fnv1a_32("test string") == h32

    h64 = fnv1a_64("test string")
    assert isinstance(h64, int)
    assert 0 <= h64 <= 0xFFFFFFFFFFFFFFFF
    assert fnv1a_64("test string") == h64


def test_rolling_hash_rabin_karp():
    text = b"abcdef"
    # Window size 3: "abc" -> "bcd"
    rh = RollingHash(window_size=3)
    h_abc = rh.feed(b"abc")
    assert h_abc == rabin_karp_hash(b"abc")

    # Slide to "bcd": drop 'a' (ord 97), add 'd' (ord 100)
    h_bcd_slide = rh.slide(ord("a"), ord("d"))
    h_bcd_direct = rabin_karp_hash(b"bcd")
    assert h_bcd_slide == h_bcd_direct
    assert rh.digest == h_bcd_direct


def test_sha256_and_hmac():
    d_hex = sha256_digest("hello", as_hex=True)
    assert isinstance(d_hex, str)
    assert len(d_hex) == 64

    d_bytes = sha256_digest("hello", as_hex=False)
    assert isinstance(d_bytes, bytes)
    assert len(d_bytes) == 32

    mac = hmac_sha256("secret_key", "payload", as_hex=True)
    assert isinstance(mac, str)
    assert len(mac) == 64


def test_file_checksum_compute_and_verify():
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"data for verification")
        path = f.name

    try:
        checksum = compute_file_checksum(path, algorithm="sha256")
        assert verify_file_checksum(path, checksum) is True
        assert verify_file_checksum(path, "0" * 64) is False
    finally:
        Path(path).unlink(missing_ok=True)


def test_merkle_tree():
    leaves = [b"tx1", b"tx2", b"tx3", b"tx4"]
    tree = MerkleTree(leaves, hash_algo="sha256")
    root = tree.root
    assert isinstance(root, str)
    assert len(root) == 64

    # Verify proof for leaf 1 ("tx2")
    proof = tree.get_proof(1)
    assert MerkleTree.verify_proof(b"tx2", proof, root) is True

    # Tampered leaf fails
    assert MerkleTree.verify_proof(b"tampered_tx2", proof, root) is False

    with pytest.raises(ValueError, match="at least one leaf"):
        MerkleTree([])
