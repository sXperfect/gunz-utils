"""Tests for gunz_utils.secure_store.SecureStore.

Relocated from ``libs/hyperhedron-google/tests/test_secure_store.py``
on 2026-06-26 (Phase 6.1 of the gunz-youtrack secure-config task).
The SecureStore implementation was promoted from
``hyperhedron_google.secure_store`` to ``gunz_utils.secure_store``;
this test file followed.
"""
import tempfile
import unittest

from gunz_utils import SecureStore


class TestSecureStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.store = SecureStore(base_dir=self._tmp)
        self.store.unlock()

    def tearDown(self):
        self.store.close()

    def test_set_and_get_round_trip(self):
        self.store.set("google.api_key", "AIza-secret")
        self.assertEqual(self.store.get("google.api_key"), "AIza-secret")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("does.not.exist"))

    def test_delete_returns_true_when_exists(self):
        self.store.set("temp", "value")
        self.assertTrue(self.store.delete("temp"))

    def test_delete_returns_false_when_missing(self):
        self.assertFalse(self.store.delete("does.not.exist"))

    def test_acl_allows_listed_caller(self):
        self.store.set("google.api_key", "secret", acl=["mcp", "cli"])
        self.assertEqual(self.store.get("google.api_key", caller="mcp"), "secret")

    def test_acl_denies_unlisted_caller(self):
        self.store.set("google.api_key", "secret", acl=["mcp"])
        with self.assertRaises(PermissionError):
            self.store.get("google.api_key", caller="library")

    def test_open_acl_allows_everyone(self):
        self.store.set("public", "value", acl=None)
        self.assertEqual(self.store.get("public", caller="anyone"), "value")

    def test_list_keys_respects_acl(self):
        self.store.set("a", "1")
        self.store.set("b", "2", acl=["mcp"])
        names = {m.name for m in self.store.list_keys(caller="library")}
        self.assertEqual(names, {"a"})

    def test_list_keys_no_filter_returns_all(self):
        self.store.set("a", "1")
        self.store.set("b", "2", acl=["mcp"])
        names = {m.name for m in self.store.list_keys(acl_filter=False)}
        self.assertEqual(names, {"a", "b"})

    def test_master_key_file_mode_0600(self):
        mode = self.store._master_key_path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_set_updates_timestamp(self):
        self.store.set("k", "v1")
        m1 = self.store.list_keys()[0]
        import time

        time.sleep(0.05)
        self.store.set("k", "v2")
        m2 = self.store.list_keys()[0]
        self.assertGreater(m2.updated_at, m1.updated_at)

    def test_passphrase_unlock_creates_salt(self):
        tmp = tempfile.mkdtemp()
        try:
            store = SecureStore(base_dir=tmp)
            store.unlock(passphrase="correct-horse-battery-staple")
            store.set("k", "v")
            store.close()

            store2 = SecureStore(base_dir=tmp)
            store2.unlock(passphrase="correct-horse-battery-staple")
            self.assertEqual(store2.get("k"), "v")
            store2.close()
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_wrong_passphrase_decrypt_fails(self):
        tmp = tempfile.mkdtemp()
        try:
            store = SecureStore(base_dir=tmp)
            store.unlock(passphrase="correct-horse-battery-staple")
            store.set("k", "v")
            store.close()

            store2 = SecureStore(base_dir=tmp)
            store2.unlock(passphrase="wrong-passphrase")
            from cryptography.fernet import InvalidToken

            with self.assertRaises(InvalidToken):
                store2.get("k")
            store2.close()
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
