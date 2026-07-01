# -*- coding: utf-8 -*-
"""
Cryptographic utilities for AES-256-GCM.
Compatible with HyperHedron CLI's TypeScript implementation.
"""

import os
import hashlib
import binascii
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Constants matching TypeScript implementation
IV_LENGTH = 12
SALT_LENGTH = 16
KEY_LENGTH = 32
ITERATIONS = 10000

def get_system_passphrase() -> str:
    """
    Derives a standard passphrase from the actual system hostname and user.
    Used for local MCP credential encryption.
    """
    hostname = os.uname().nodename
    username = os.environ.get("USER", "sxperfect")
    return f"{hostname}:{username}:hyperhedron-mcp"

def get_derived_key(salt: bytes, passphrase: str | None = None) -> bytes:
    """
    Derives a machine-unique encryption key.
    Replicates TypeScript's getDerivedKey logic.
    """
    hostname = os.uname().nodename
    machine_secret = hashlib.sha256(hostname.encode('utf-8')).hexdigest()
    
    final_passphrase = f"{passphrase}:{machine_secret}" if passphrase else machine_secret
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(final_passphrase.encode('utf-8'))

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
    
    return f"{salt.hex()}:{iv.hex()}:{tag.hex()}:{encrypted.hex()}"

def decrypt(encrypted_text: str, passphrase: str | None = None) -> str:
    """
    Decrypts a string using AES-256-GCM.
    Input format: salt:iv:tag:encryptedPayload (all hex)
    If the text doesn't start with 'aes256:', returns it as-is (unencrypted).
    """
    if not encrypted_text.startswith("aes256:"):
        return encrypted_text

    encrypted_text = encrypted_text.replace("aes256:", "")
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
