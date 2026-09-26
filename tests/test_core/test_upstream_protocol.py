"""Tests for ``gunz_utils.upstream_protocol``.

Covers:
    * Exception hierarchy (UpstreamError + 4 subclasses, to_dict envelope)
    * UpstreamClient Protocol (runtime_checkable, isinstance works)
    * BaseUpstream (abstract _invoke, default call/health_check/close)

These tests live in ``test_core/`` because the protocol + exception
hierarchy are zero-dependency (stdlib only).
"""
import asyncio
import unittest

from gunz_utils.upstream_protocol import (
    BaseUpstream,
    PolicyUpstream,
    UpstreamAuthError,
    UpstreamClient,
    UpstreamError,
    UpstreamNotFoundError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestUpstreamError(unittest.TestCase):
    """``UpstreamError`` is the broker-facing base class."""

    def test_required_fields_stored(self):
        err = UpstreamError("boom", upstream="jules")
        self.assertEqual(err.upstream, "jules")
        self.assertIsNone(err.tool_name)
        self.assertEqual(err.message, "boom")
        self.assertEqual(str(err), "boom")

    def test_optional_tool_name_stored(self):
        err = UpstreamError("boom", upstream="wikijs", tool_name="search")
        self.assertEqual(err.tool_name, "search")

    def test_to_dict_envelope(self):
        err = UpstreamError("kaboom", upstream="docs", tool_name="render")
        envelope = err.to_dict()
        self.assertEqual(
            envelope,
            {
                "error": "kaboom",
                "upstream": "docs",
                "tool_name": "render",
                "error_type": "UpstreamError",
            },
        )

    def test_to_dict_omits_tool_name_when_none(self):
        #? tool_name is metadata; absence must serialise as None, not be hidden
        err = UpstreamError("oops", upstream="jules")
        self.assertIsNone(err.to_dict()["tool_name"])


class TestUpstreamErrorSubclasses(unittest.TestCase):
    """Each subclass must be catchable as UpstreamError and carry its own type."""

    cases = [
        (UpstreamTimeoutError, "UpstreamTimeoutError"),
        (UpstreamAuthError, "UpstreamAuthError"),
        (UpstreamNotFoundError, "UpstreamNotFoundError"),
        (UpstreamUnavailableError, "UpstreamUnavailableError"),
    ]

    def test_each_is_upstream_error(self):
        for cls, _ in self.cases:
            with self.subTest(cls=cls):
                err = cls("x", upstream="svc")
                self.assertIsInstance(err, UpstreamError)

    def test_each_serialises_with_own_type(self):
        for cls, type_name in self.cases:
            with self.subTest(cls=cls):
                err = cls("x", upstream="svc", tool_name="t")
                self.assertEqual(err.to_dict()["error_type"], type_name)


# ---------------------------------------------------------------------------
# UpstreamClient Protocol (runtime_checkable)
# ---------------------------------------------------------------------------


class _ValidImpl:
    """Minimal duck-typed implementation of UpstreamClient."""

    name = "demo"

    async def call(self, tool_name, arguments):
        return {"tool": tool_name, "echo": arguments}

    async def health_check(self):
        return True

    async def close(self):
        return None


class _MissingMethodImpl:
    """Lacks ``close()``; should NOT satisfy the Protocol."""

    name = "broken"

    async def call(self, tool_name, arguments):
        return {}

    async def health_check(self):
        return True


class TestUpstreamClientProtocol(unittest.TestCase):
    """``UpstreamClient`` is ``@runtime_checkable`` so isinstance works."""

    def test_valid_impl_passes_isinstance(self):
        self.assertIsInstance(_ValidImpl(), UpstreamClient)

    def test_impl_missing_close_fails_isinstance(self):
        #? ``@runtime_checkable`` only checks method presence, not signatures —
        #? this is the documented contract for Protocol runtime checks.
        self.assertNotIsInstance(_MissingMethodImpl(), UpstreamClient)

    def test_non_upstream_object_fails_isinstance(self):
        self.assertNotIsInstance("not an upstream", UpstreamClient)
        self.assertNotIsInstance({}, UpstreamClient)


# ---------------------------------------------------------------------------
# BaseUpstream convenience base class
# ---------------------------------------------------------------------------


class _ConcreteUpstream(BaseUpstream):
    """Minimal concrete subclass used to exercise BaseUpstream defaults."""

    name = "concrete"

    async def _invoke(self, tool_name, arguments):
        return {"name": self.name, "tool": tool_name, "args": arguments}


class TestBaseUpstream(unittest.TestCase):
    """``BaseUpstream`` provides default call/health_check/close."""

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            #? BaseUpstream is abstract: _invoke has no implementation.
            BaseUpstream()  # noqa: B033

    def test_default_name_is_unnamed(self):
        class _Anon(BaseUpstream):
            async def _invoke(self, tool_name, arguments):
                return {}

        self.assertEqual(_Anon().name, "unnamed")

    def test_call_delegates_to_invoke(self):
        upstream = _ConcreteUpstream()

        import asyncio

        result = asyncio.run(
            upstream.call("render", {"page": "home"})
        )
        self.assertEqual(
            result,
            {"name": "concrete", "tool": "render", "args": {"page": "home"}},
        )

    def test_default_health_check_returns_true(self):
        upstream = _ConcreteUpstream()
        import asyncio

        self.assertTrue(asyncio.run(upstream.health_check()))

    def test_default_close_returns_none(self):
        upstream = _ConcreteUpstream()
        import asyncio

        self.assertIsNone(asyncio.run(upstream.close()))

    def test_subclass_can_override_health_check(self):
        class _Flaky(BaseUpstream):
            async def _invoke(self, tool_name, arguments):
                return {}

            async def health_check(self):
                return False

        import asyncio

        self.assertFalse(asyncio.run(_Flaky().health_check()))


class TestPolicyUpstream(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_is_translated(self) -> None:
        class Slow:
            name = "slow"

            async def call(self, tool_name, arguments):
                await asyncio.sleep(0.05)
                return {}

            async def health_check(self):
                return True

            async def close(self):
                return None

        wrapped = PolicyUpstream(Slow(), timeout_seconds=0.001)
        with self.assertRaises(UpstreamTimeoutError):
            await wrapped.call("read", {})

    async def test_retry_requires_explicit_idempotent_tool(self) -> None:
        class Flaky:
            name = "flaky"

            def __init__(self):
                self.calls = 0

            async def call(self, tool_name, arguments):
                self.calls += 1
                if self.calls == 1:
                    raise UpstreamUnavailableError("retry", upstream=self.name)
                return {"ok": True}

            async def health_check(self):
                return True

            async def close(self):
                return None

        client = Flaky()
        wrapped = PolicyUpstream(
            client, max_attempts=2, idempotent_tools=frozenset({"read"})
        )
        self.assertEqual(await wrapped.call("read", {}), {"ok": True})
        self.assertEqual(wrapped.stats["retries"], 1)


if __name__ == "__main__":
    unittest.main()
