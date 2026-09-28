"""Tests for gunz_utils.secure_store.SecureStore.

Relocated from ``libs/hyperhedron-google/tests/test_secure_store.py``
on 2026-06-26 (Phase 6.1 of the gunz-youtrack secure-config task).
The SecureStore implementation was promoted from
``hyperhedron_google.secure_store`` to ``gunz_utils.secure_store``;
this test file followed.
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gunz_utils import SecureStore
from gunz_utils.ext.secure_store import default_base_dir


class TestSecureStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.store = SecureStore(base_dir=self._tmp)
        self.store.unlock()

    def tearDown(self):
        self.store.close()

    def test_connection_has_bounded_busy_timeout(self):
        value = self.store._conn.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]
        self.assertEqual(value, 10000)

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
            from cryptography.fernet import InvalidToken

            with self.assertRaises(InvalidToken):
                store2.unlock(passphrase="wrong-passphrase")
            store2.close()
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_acl_blocks_overwrite_and_delete(self):
        self.store.set("protected", "value", caller="mcp", acl=["mcp"])
        with self.assertRaises(PermissionError):
            self.store.set("protected", "changed", caller="library")
        with self.assertRaises(PermissionError):
            self.store.delete("protected", caller="library")
        self.assertEqual(self.store.get("protected", caller="mcp"), "value")

    def test_existing_acl_is_preserved_when_omitted(self):
        self.store.set("protected", "one", caller="mcp", acl=["mcp"])
        self.store.set("protected", "two", caller="mcp")
        with self.assertRaises(PermissionError):
            self.store.get("protected", caller="library")

    def test_delete_requires_unlock(self):
        self.store.set("protected", "value")
        self.store.lock()
        with self.assertRaises(RuntimeError):
            self.store.delete("protected")

    def test_binary_round_trip(self):
        payload = b"\xff\x00secret"
        self.store.set("binary", payload)
        self.assertEqual(self.store.get_bytes("binary"), payload)

    def test_passphrase_store_requires_passphrase(self):
        tmp = tempfile.mkdtemp()
        try:
            store = SecureStore(base_dir=tmp)
            store.unlock(passphrase="correct-horse-battery-staple")
            store.set("k", "v")
            store.close()
            store2 = SecureStore(base_dir=tmp)
            with self.assertRaises(RuntimeError):
                store2.unlock()
            store2.close()
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bulk_round_trip_and_audit_query(self):
        self.store.set_many({"a": "1", "b": "2"})
        self.assertEqual(self.store.get_many(["a", "b"]), {"a": "1", "b": "2"})
        events = self.store.audit_events(limit=10)
        self.assertTrue(any(event["action"] == "set" for event in events))

    def test_context_manager_closes_store(self):
        tmp = tempfile.mkdtemp()
        try:
            with SecureStore(base_dir=tmp) as store:
                store.unlock()
                store.set("k", "v")
            with self.assertRaises(sqlite3.ProgrammingError):
                store.list_keys()
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


    def test_rejects_empty_passphrase(self):
        tmp = tempfile.mkdtemp()
        try:
            store = SecureStore(base_dir=tmp)
            with self.assertRaisesRegex(ValueError, "passphrase"):
                store.unlock(passphrase="")
            self.assertFalse(store._salt_path.exists())
            store.close()
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def test_rejects_invalid_library_name(self):
        with self.assertRaisesRegex(ValueError, "library_name"):
            default_base_dir("../escape")
        with self.assertRaisesRegex(ValueError, "library_name"):
            default_base_dir("nested/name")

    def test_rejects_acl_delimiter_injection(self):
        with self.assertRaisesRegex(ValueError, "ACL entry"):
            self.store.set("k", "v", acl=["mcp,library"])
        with self.assertRaisesRegex(ValueError, "caller"):
            self.store.set("k", "v", caller="mcp,library")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_symlink_base_directory(self):
        root = Path(tempfile.mkdtemp())
        target = root / "target"
        target.mkdir()
        link = root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable")
        try:
            with self.assertRaisesRegex(ValueError, "base directory"):
                SecureStore(base_dir=link)
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_symlink_master_key(self):
        root = Path(tempfile.mkdtemp())
        outside = root / "outside.key"
        outside.write_bytes(b"x" * 44)
        store_dir = root / "store"
        store = SecureStore(base_dir=store_dir)
        link = store._master_key_path
        try:
            link.symlink_to(outside)
        except OSError:
            store.close()
            self.skipTest("symlink creation unavailable")
        try:
            with self.assertRaisesRegex(ValueError, "symlink"):
                store.unlock()
        finally:
            store.close()
            import shutil

            shutil.rmtree(root, ignore_errors=True)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_symlink_database(self):
        root = Path(tempfile.mkdtemp())
        store_dir = root / "store"
        store_dir.mkdir()
        outside = root / "outside.db"
        outside.write_bytes(b"")
        link = store_dir / "config.db"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation unavailable")
        try:
            with self.assertRaisesRegex(ValueError, "database path"):
                SecureStore(base_dir=store_dir)
        finally:
            import shutil

            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
