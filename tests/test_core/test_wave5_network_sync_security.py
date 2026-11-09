"""Tests for Wave 5: Network, sync, diagnostics, notebook/project, security, redaction, content_store, and provenance."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from gunz_utils.content_store import ContentAddressedStore
from gunz_utils.diagnostics import exception_dict
from gunz_utils.network import _is_non_public_address, build_network_uri, tcp_reachable
from gunz_utils.notebook import setup_notebook
from gunz_utils.project import resolve_project_root
from gunz_utils.provenance import ExecutionManifest, GitInfo, RuntimeProvenance
from gunz_utils.redaction import SECRET_PATTERNS, redact
from gunz_utils.security import is_safe_relative_path
from gunz_utils.sync import _unsafe_rsync_extra_argument, rsync_mirror


class TestNetworkWave5(unittest.TestCase):
    def test_build_network_uri_control_chars_and_query_validation(self) -> None:
        with self.assertRaises(ValueError):
            build_network_uri("http", "example.com", username="admin\r\nInjected: True")
        with self.assertRaises(ValueError):
            build_network_uri("http", "example.com", username="admin", password="pw\n")
        with self.assertRaises(TypeError):
            build_network_uri("http", "example.com", username=123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            build_network_uri("http", "example.com", query="bare_query_string")  # type: ignore[arg-type]

        uri = build_network_uri("https", "example.com", username="user", password="secret", query={"q": "test"})
        self.assertEqual(uri, "https://user:secret@example.com?q=test")

    def test_ipv4_mapped_ipv6_detection(self) -> None:
        self.assertTrue(_is_non_public_address("::ffff:127.0.0.1"))
        self.assertTrue(_is_non_public_address("::ffff:192.168.1.1"))
        self.assertFalse(_is_non_public_address("8.8.8.8"))


class TestSyncWave5(unittest.TestCase):
    def test_unsafe_rsync_extra_args(self) -> None:
        self.assertTrue(_unsafe_rsync_extra_argument("--daemon"))
        self.assertTrue(_unsafe_rsync_extra_argument("--config=/etc/rsync.conf"))
        self.assertTrue(_unsafe_rsync_extra_argument("--dparam=foo=bar"))

    def test_rsync_mirror_target_validation(self) -> None:
        with self.assertRaises(ValueError):
            rsync_mirror("source_dir", "-rf")
        with self.assertRaises(ValueError):
            rsync_mirror("source_dir", "target\0dir")


class TestDiagnosticsWave5(unittest.TestCase):
    def test_exception_dict_redaction_and_validation(self) -> None:
        with self.assertRaises(TypeError):
            exception_dict("not_an_exc")  # type: ignore[arg-type]

        exc = ValueError("some error")
        data = exception_dict(exc, include_message=True, context={"api_key": "my-secret-key"})
        self.assertNotIn("my-secret-key", str(data))
        self.assertEqual(data["message"], "some error")
        self.assertEqual(data["context"]["api_key"], "****")


class TestSecurityWave5(unittest.TestCase):
    def test_is_safe_relative_path(self) -> None:
        self.assertTrue(is_safe_relative_path("safe/path/to/file.txt"))
        self.assertTrue(is_safe_relative_path(Path("nested/dir/doc.pdf")))

        self.assertFalse(is_safe_relative_path("../outside.txt"))
        self.assertFalse(is_safe_relative_path("/root/abs.txt"))
        self.assertFalse(is_safe_relative_path("C:\\windows\\win32.dll"))
        self.assertFalse(is_safe_relative_path("foo/bar/\0/baz"))
        self.assertFalse(is_safe_relative_path(""))
        self.assertFalse(is_safe_relative_path(None))  # type: ignore[arg-type]


class TestRedactionWave5(unittest.TestCase):
    def test_secret_patterns_jwt_and_bearer(self) -> None:
        self.assertIn("jwt", SECRET_PATTERNS)
        self.assertIn("bearer", SECRET_PATTERNS)
        self.assertIn("id_token", SECRET_PATTERNS)


class TestContentStoreWave5(unittest.TestCase):
    def test_store_contains(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContentAddressedStore(Path(tmpdir))
            art = store.put_bytes(b"hello content store")
            self.assertIn(art.digest, store)
            self.assertNotIn("0" * 64, store)
            self.assertNotIn(12345, store)


class TestProvenanceWave5(unittest.TestCase):
    def test_execution_manifest_redacts_config(self) -> None:
        runtime = RuntimeProvenance(
            captured_at="2026-01-01T00:00:00Z",
            python_version="3.11",
            python_implementation="CPython",
            platform="Linux",
            machine="x86_64",
            executable="/usr/bin/python3",
        )
        git = GitInfo(commit="abc1234", branch="main", dirty=False)
        manifest = ExecutionManifest(
            created_at="2026-01-01T00:00:00Z",
            run_id="run-1",
            runtime=runtime,
            git=git,
            config={"api_key": "super_secret_key", "batch_size": 32},
        )
        self.assertEqual(manifest.config["api_key"], "****")
        self.assertEqual(manifest.config["batch_size"], 32)


if __name__ == "__main__":
    unittest.main()
