"""
Cryptographic utilities for AES-256-GCM.
Compatible with HyperHedron CLI's TypeScript implementation.
"""
# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
import binascii
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .._version import __version__ as __version__
from ..deprecation import deprecated

# Constants matching TypeScript implementation
IV_LENGTH = 12
SALT_LENGTH = 16
KEY_LENGTH = 32
ITERATIONS = 600_000
_FORMAT_PREFIX = "aes256:v2:"

@deprecated(
    "get_system_passphrase() is predictable machine identity, not secret key "
    "material; provide an explicit high-entropy passphrase instead"
)
def get_system_passphrase() -> str:
    """Return the legacy predictable hostname/user identifier.

    This value is retained only for compatibility and must not be used as a
    cryptographic secret. New encryption calls require an explicit passphrase.
    """
    hostname = os.uname().nodename
    username = os.environ.get("USER", "sxperfect")
    return f"{hostname}:{username}:hyperhedron-mcp"

def get_derived_key(salt: bytes, passphrase: str | None = None) -> bytes:
    """Derive an AES key from explicit secret material."""
    if not passphrase:
        raise ValueError("passphrase is required for encryption")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(passphrase.encode("utf-8"))

def encrypt(text: str, passphrase: str | None = None) -> str:
    """
    Encrypts a string using AES-256-GCM.
    Output format: salt:iv:tag:encryptedPayload (all hex)
    """
    salt = os.urandom(SALT_LENGTH)
    iv = os.urandom(IV_LENGTH)
    key = get_derived_key(salt, passphrase)

    aesgcm = AESGCM(key)
    # cryptography's AESGCM.encrypt appends the tag to the ciphertext
    ciphertext_with_tag = aesgcm.encrypt(iv, text.encode('utf-8'), None)

    # Split tag (last 16 bytes) and ciphertext
    tag = ciphertext_with_tag[-16:]
    encrypted = ciphertext_with_tag[:-16]

    return f"{_FORMAT_PREFIX}{salt.hex()}:{iv.hex()}:{tag.hex()}:{encrypted.hex()}"

def decrypt(encrypted_text: str, passphrase: str | None = None) -> str:
    """
    Decrypts a string using AES-256-GCM.
    Input format: salt:iv:tag:encryptedPayload (all hex)
    If the text doesn't start with 'aes256:', returns it as-is (unencrypted).
    """
    if not encrypted_text.startswith("aes256:"):
        return encrypted_text
    if encrypted_text.startswith(_FORMAT_PREFIX):
        encrypted_text = encrypted_text[len(_FORMAT_PREFIX):]
    else:
        raise ValueError(
            "Legacy aes256 ciphertext uses insecure hostname-derived key material; "
            "migrate it with an older trusted client before decrypting here"
        )
    parts = encrypted_text.split(':')
    if len(parts) != 4:
        raise ValueError("Invalid encrypted format")

    salt = binascii.unhexlify(parts[0])
    iv = binascii.unhexlify(parts[1])
    tag = binascii.unhexlify(parts[2])
    encrypted = binascii.unhexlify(parts[3])

    key = get_derived_key(salt, passphrase)
    aesgcm = AESGCM(key)

    # cryptography expects ciphertext + tag
    decrypted = aesgcm.decrypt(iv, encrypted + tag, None)

    return decrypted.decode('utf-8')
