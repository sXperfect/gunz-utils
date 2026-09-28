"""Security regression tests for AES-GCM helpers."""

from __future__ import annotations

import unittest
import warnings
from unittest.mock import patch

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

    def test_key_derivation_rejects_invalid_salt_length(self) -> None:
        with self.assertRaisesRegex(ValueError, "salt"):
            get_derived_key(b"short", "test-passphrase")

    def test_legacy_ciphertext_is_not_silently_decrypted(self) -> None:
        with self.assertRaises(ValueError):
            decrypt("aes256:00:00:00:00", passphrase="test-passphrase")

    def test_system_passphrase_fails_closed(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", GunzDeprecationWarning)
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                get_system_passphrase()
        self.assertTrue(caught)
        self.assertIs(caught[0].category, GunzDeprecationWarning)

    def test_plaintext_is_rejected_by_default(self) -> None:
        with self.assertRaisesRegex(ValueError, "authenticated aes256"):
            decrypt("plain-text")

    def test_plaintext_passthrough_requires_explicit_migration_opt_in(self) -> None:
        self.assertEqual(
            decrypt("plain-text", allow_plaintext=True),
            "plain-text",
        )

    def test_invalid_component_lengths_are_rejected_before_kdf(self) -> None:
        payload = (
            "aes256:v2:00:"
            "000000000000000000000000:"
            "00000000000000000000000000000000:00"
        )
        with patch(
            "gunz_utils.ext.secure_crypto.get_derived_key",
            side_effect=AssertionError("KDF must not run"),
        ):
            with self.assertRaisesRegex(ValueError, "Invalid encrypted format"):
                decrypt(
                    payload,
                    passphrase="test-passphrase",
                )

    def test_malformed_hex_is_normalized_to_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid encrypted format"):
            decrypt(
                "aes256:v2:zz:00:00:00",
                passphrase="test-passphrase",
            )


if __name__ == "__main__":
    unittest.main()
