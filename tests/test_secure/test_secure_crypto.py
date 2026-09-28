"""Security regression tests for AES-GCM helpers."""

from __future__ import annotations

import unittest
import warnings

from gunz_utils.deprecation import GunzDeprecationWarning
from gunz_utils.ext.secure_crypto import (
    decrypt,
    encrypt,
    get_derived_key,
    get_system_passphrase,
)


class TestSecureCrypto(unittest.TestCase):
    def test_round_trip_requires_explicit_passphrase(self) -> None:
        encrypted = encrypt("synthetic-secret", passphrase="test-passphrase")
        self.assertTrue(encrypted.startswith("aes256:v2:"))
        self.assertEqual(
            decrypt(encrypted, passphrase="test-passphrase"),
            "synthetic-secret",
        )

    def test_encrypt_without_passphrase_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            encrypt("synthetic-secret")

    def test_key_derivation_without_passphrase_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_derived_key(b"0" * 16)

    def test_legacy_ciphertext_is_not_silently_decrypted(self) -> None:
        with self.assertRaises(ValueError):
            decrypt("aes256:00:00:00:00", passphrase="test-passphrase")

    def test_system_passphrase_is_explicitly_deprecated(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", GunzDeprecationWarning)
            value = get_system_passphrase()
        self.assertIsInstance(value, str)
        self.assertTrue(caught)
        self.assertIs(caught[0].category, GunzDeprecationWarning)

    def test_plaintext_passthrough_is_preserved(self) -> None:
        self.assertEqual(decrypt("plain-text"), "plain-text")


if __name__ == "__main__":
    unittest.main()
