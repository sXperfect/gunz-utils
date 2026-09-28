"""Cryptographic utilities for AES-256-GCM.

The wire format remains compatible with the HyperHedron TypeScript client.
"""

from __future__ import annotations

import binascii
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .._version import __version__ as __version__
from ..deprecation import deprecated

IV_LENGTH = 12
SALT_LENGTH = 16
KEY_LENGTH = 32
ITERATIONS = 600_000
_FORMAT_PREFIX = "aes256:v2:"


@deprecated(
    "get_system_passphrase() used predictable machine identity as secret key "
    "material and now fails closed; provide an explicit high-entropy passphrase"
)
def get_system_passphrase() -> str:
    """Reject the legacy predictable hostname/user passphrase derivation."""
    raise RuntimeError(
        "predictable system-derived passphrases are disabled; "
        "provide an explicit high-entropy passphrase"
    )


def get_derived_key(salt: bytes, passphrase: str | None = None) -> bytes:
    """Derive an AES key from explicit secret material."""
    if not isinstance(salt, bytes) or len(salt) != SALT_LENGTH:
        raise ValueError(f"salt must be exactly {SALT_LENGTH} bytes")
    if not isinstance(passphrase, str) or not passphrase:
        raise ValueError("passphrase is required for encryption")

    # Security (VULN-2026-012): keep passphrases out of process-wide caches.
    # Callers exposing repeated decrypt attempts must additionally rate-limit
    # those attempts; varying attacker-controlled salts defeats key caching.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(text: str, passphrase: str | None = None) -> str:
    """Encrypt a UTF-8 string using AES-256-GCM."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    salt = os.urandom(SALT_LENGTH)
    iv = os.urandom(IV_LENGTH)
    key = get_derived_key(salt, passphrase)

    ciphertext_with_tag = AESGCM(key).encrypt(iv, text.encode("utf-8"), None)
    tag = ciphertext_with_tag[-16:]
    encrypted = ciphertext_with_tag[:-16]
    return f"{_FORMAT_PREFIX}{salt.hex()}:{iv.hex()}:{tag.hex()}:{encrypted.hex()}"


def decrypt(
    encrypted_text: str,
    passphrase: str | None = None,
    *,
    allow_plaintext: bool = False,
) -> str:
    """Decrypt authenticated AES-256-GCM ciphertext.

    Plaintext input is rejected by default so callers cannot accidentally
    downgrade from authenticated encryption to unauthenticated data. Migration
    code may opt in explicitly with ``allow_plaintext=True``.
    """
    if not isinstance(encrypted_text, str):
        raise TypeError("encrypted_text must be a string")
    if not isinstance(allow_plaintext, bool):
        raise TypeError("allow_plaintext must be bool")

    if not encrypted_text.startswith("aes256:"):
        if allow_plaintext:
            return encrypted_text
        raise ValueError(
            "ciphertext is not authenticated aes256 data; "
            "set allow_plaintext=True only for explicit migration"
        )
    if encrypted_text.startswith(_FORMAT_PREFIX):
        payload = encrypted_text[len(_FORMAT_PREFIX):]
    else:
        raise ValueError(
            "Legacy aes256 ciphertext uses insecure hostname-derived key material; "
            "migrate it with an older trusted client before decrypting here"
        )

    parts = payload.split(":")
    if len(parts) != 4:
        raise ValueError("Invalid encrypted format")
    try:
        salt = binascii.unhexlify(parts[0])
        iv = binascii.unhexlify(parts[1])
        tag = binascii.unhexlify(parts[2])
        encrypted = binascii.unhexlify(parts[3])
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid encrypted format") from exc
    if len(salt) != SALT_LENGTH or len(iv) != IV_LENGTH or len(tag) != 16:
        raise ValueError("Invalid encrypted format")

    key = get_derived_key(salt, passphrase)
    decrypted = AESGCM(key).decrypt(iv, encrypted + tag, None)
    return decrypted.decode("utf-8")
