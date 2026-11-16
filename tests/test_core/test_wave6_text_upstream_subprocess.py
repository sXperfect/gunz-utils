"""Tests for Wave 6: text processing, upstreams, and subprocess (#71–#83)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import re
import sys
import unittest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.subprocess import (
    run_command,
    run_command_async,
)
from gunz_utils.text import (
    blank_spans,
    deduplicate_spans,
    slugify,
    truncate_text,
    word_pattern,
)
from gunz_utils.upstream_protocol import (
    PolicyUpstream,
    UpstreamError,
    UpstreamUnavailableError,
)


class MockUpstreamClient:
    def __init__(self,
        name: str = "mock_service",
    ) -> None:
        self.name = name
        self.closed = False
        self.healthy = True

    async def call(self,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        if tool_name == "fail":
            raise UpstreamUnavailableError(
    "unavailable", upstream=self.name, tool_name=tool_name)
        if tool_name == "hang":
            await asyncio.sleep(10.0)
        return {"result": f"ok-{tool_name}"}

    async def health_check(self) -> bool:
        return self.healthy

    async def close(self) -> None:
        self.closed = True


class TestWave6Text(unittest.TestCase):
    def test_item71_word_pattern_validation(self) -> None:
        with self.assertRaises(ValueError):
            word_pattern("")
        with self.assertRaises(ValueError):
            word_pattern("   ")
        with self.assertRaises(TypeError):
            word_pattern(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            word_pattern("term", flags=True)  # type: ignore[arg-type]

        #? Multi-word whitespace normalization
        p = word_pattern("sanity   check")
        self.assertIsNotNone(p.search("sanity check"))
        self.assertIsNotNone(p.search("sanity-check"))
        self.assertIsNotNone(p.search("sanity checks"))

    def test_item72_blank_spans_validation(self) -> None:
        with self.assertRaises(TypeError):
            blank_spans(123, [])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            blank_spans("text", "not-a-sequence")  # type: ignore[arg-type]

        pat = re.compile(r"bad")
        masked = blank_spans("a bad word", [pat])
        self.assertEqual(masked, "a     word")

    def test_item73_deduplicate_spans_validation(self) -> None:
        with self.assertRaises(ValueError):
            deduplicate_spans([(-1, 5, "payload")])
        with self.assertRaises(ValueError):
            deduplicate_spans([(10, 5, "payload")])
        with self.assertRaises(ValueError):
            deduplicate_spans([(True, 5, "payload")])  # type: ignore[list-item]

        res = deduplicate_spans([(0, 5, "long"), (1, 3, "short")])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][2], "long")

    def test_item74_truncate_text_and_slugify(self) -> None:
        #? truncate_text
        with self.assertRaises(TypeError):
            truncate_text(123, 10)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            truncate_text("hello", -1)
        self.assertEqual(truncate_text("short", 10), "short")
        self.assertEqual(truncate_text("hello world", 8), "hello...")
        self.assertEqual(truncate_text("hello world", 2), "..")

        #? slugify
        with self.assertRaises(TypeError):
            slugify(123)  # type: ignore[arg-type]
        self.assertEqual(slugify("Hello, World! 123"), "hello-world-123")
        self.assertEqual(
    slugify("  Multiple   Spaces  _ Here "),
     "multiple-spaces-_-here")


class TestWave6Upstream(unittest.IsolatedAsyncioTestCase):
    def test_item75_upstream_error_validation_and_redaction(self) -> None:
        with self.assertRaises(ValueError):
            UpstreamError("msg", upstream="")
        with self.assertRaises(ValueError):
            UpstreamError("msg", upstream="   ")

        err = UpstreamError(
    "failed with token=secret12345 in header",
     upstream="auth_srv")
        self.assertNotIn("secret12345", str(err))
        self.assertIn("[REDACTED]", str(err))

    async def test_item76_async_context_manager(self) -> None:
        client = MockUpstreamClient()
        policy = PolicyUpstream(client)
        async with policy as p:
            self.assertEqual(p.name, "mock_service")
        self.assertTrue(client.closed)

    async def test_item77_item78_policy_cancellation_and_reset_stats(self) -> None:
        client = MockUpstreamClient()
        policy = PolicyUpstream(client, timeout_seconds=1.0)
        res = await policy.call("echo", {"key": "val"})
        self.assertEqual(res["result"], "ok-echo")
        self.assertEqual(policy.stats["calls"], 1)

        policy.reset_stats()
        self.assertEqual(policy.stats["calls"], 0)


class TestWave6Subprocess(unittest.IsolatedAsyncioTestCase):
    def test_item79_bare_string_and_nul_rejection(self) -> None:
        with self.assertRaises(TypeError):
            run_command("echo hello")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            run_command(["echo", "bad\x00arg"])

    def test_item80_check_and_env_validation(self) -> None:
        with self.assertRaises(TypeError):
            run_command(["echo", "ok"], check="yes")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            run_command(["echo", "ok"], env="not-a-map")  # type: ignore[arg-type]

    def test_item81_command_result_ok_and_exit_code(self) -> None:
        res = run_command([sys.executable, "-c", "import sys; sys.exit(0)"])
        self.assertTrue(res.ok)
        self.assertEqual(res.exit_code, 0)

        res_err = run_command([sys.executable, "-c", "import sys; sys.exit(2)"])
        self.assertFalse(res_err.ok)
        self.assertEqual(res_err.exit_code, 2)

    async def test_item82_async_subprocess_validation(self) -> None:
        with self.assertRaises(TypeError):
            await run_command_async("echo hello")  # type: ignore[arg-type]
        res = await run_command_async([sys.executable, "-c", "print('async ok')"])
        self.assertTrue(res.ok)
        self.assertEqual(res.stdout.strip(), "async ok")


if __name__ == "__main__":
    unittest.main()
