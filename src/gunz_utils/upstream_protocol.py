"""
Upstream Protocol + exception hierarchy for MCP wrapper libraries.

This module is the canonical, library-agnostic definition of the
``UpstreamClient`` Protocol. Any domain library (e.g.
``gunz-youtrack``, ``gunz-wikijs``, ``gunz-jules``) can implement
this Protocol without importing ``hyperhedron-core``. The Broker
in ``hyperhedron-core`` re-exports these symbols so existing
imports of ``from hyperhedron_mcp.upstream.base import UpstreamError``
continue to work.

Why a Protocol (not ABC):
    - Structural typing — agents don't need to import this module to
      implement it.
    - Type checkers (mypy) catch missing methods without runtime
      enforcement.
    - Lighter than ABC (no __init_subclass__ machinery).

Why one ``.call()`` method (not 49 per class):
    - Simpler dispatch logic in the Broker.
    - No need to regenerate the Protocol when new tools are added.
    - Trade-off: less static type safety per call (mitigated by
      Pydantic models in input_schema).

Usage
-----
Implement the Protocol directly::

    from gunz_utils.upstream_protocol import UpstreamClient

    class MyUpstream:
        name: str = "my_service"

        async def call(self, tool_name, arguments):
            ...
        async def health_check(self):
            return True
        async def close(self):
            return None

Or subclass ``BaseUpstream`` for the default error handling +
``call()`` boilerplate::

    from gunz_utils.upstream_protocol import BaseUpstream

    class MyUpstream(BaseUpstream):
        name = "my_service"

        async def _invoke(self, tool_name, arguments):
            ...

Note
----
``BaseUpstream.call()`` returns ``await self._invoke(...)`` verbatim
with no error wrapping. Upstream-specific error translation (e.g.
``YouTrackAuthError -> UpstreamAuthError``) is the responsibility of
the subclass.
"""

from __future__ import annotations

import abc
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class UpstreamError(Exception):
    """Base class for all upstream failures. Catch this in the Broker.

    Parameters
    ----------
    message : str
        Human-readable error description.
    upstream : str
        Identifier of the upstream (e.g. ``"youtrack"``).
    tool_name : str | None
        The MCP tool name that triggered the failure, if applicable.
    """

    def __init__(
        self,
        message: str,
        *,
        upstream: str,
        tool_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.upstream = upstream
        self.tool_name = tool_name
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.message,
            "upstream": self.upstream,
            "tool_name": self.tool_name,
            "error_type": type(self).__name__,
        }


class UpstreamTimeoutError(UpstreamError):
    """Per-call timeout exceeded (``asyncio.wait_for`` fired)."""


class UpstreamAuthError(UpstreamError):
    """Credentials missing, expired, or rejected by the upstream."""


class UpstreamNotFoundError(UpstreamError):
    """Tool name unknown to this upstream, or required argument missing."""


class UpstreamUnavailableError(UpstreamError):
    """Upstream is in circuit-open state or otherwise refusing calls."""


# ---------------------------------------------------------------------------
# Protocol — the contract any upstream wrapper must satisfy
# ---------------------------------------------------------------------------


@runtime_checkable
class UpstreamClient(Protocol):
    """Uniform interface that all upstream wrappers must implement.

    Implementations are typically thin wrappers around an async client
    class from a domain library (e.g. ``gunz_youtrack.YouTrackClient``,
    ``gunz_wikijs.WikiJSClient``).

    Method semantics::

        async call(tool_name, arguments) -> dict
            Dispatch a tool invocation to the underlying client.
            Returns a JSON-serialisable dict on success.
            Raises UpstreamError subclasses on failure.

        async health_check() -> bool
            Cheap liveness probe used by the Broker at startup
            and on circuit-breaker half-open transitions.

        async close() -> None
            Release resources (HTTP clients, connection pools).
            Called by the Broker at shutdown.
    """

    name: str  # e.g., "jules", "wikijs", "docs", ...

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke ``tool_name`` on this upstream with ``arguments``.

        Args:
            tool_name: One of the tool names registered for this upstream.
            arguments: The JSON-decoded arguments dict from the MCP client.

        Returns:
            JSON-serialisable dict with the result payload.

        Raises:
            UpstreamNotFoundError: tool_name not in this upstream's tool set.
            UpstreamAuthError: credentials missing/expired.
            UpstreamTimeoutError: underlying call took too long.
            UpstreamError: any other failure (network, 5xx, validation, ...).
        """
        ...

    async def health_check(self) -> bool:
        """Return True if the upstream is reachable and credentials are valid."""
        ...

    async def close(self) -> None:
        """Release any held resources (HTTP clients, connection pools, etc.)."""
        ...


# ---------------------------------------------------------------------------
# Optional convenience base class (NOT required by the Protocol)
# ---------------------------------------------------------------------------


class BaseUpstream(abc.ABC):
    """Optional convenience base class. Not required by ``UpstreamClient``.

    Subclasses should:
        1. Set ``self.name`` (e.g. ``"wikijs"``).
        2. Implement ``async def _invoke(self, tool_name, arguments) -> dict``
           which contains the actual tool_name -> method dispatch logic.
        3. Optionally override ``health_check()`` and ``close()``.

    The default ``call()`` delegates to ``_invoke`` with no error
    wrapping — upstream-specific error translation (e.g.
    ``YouTrackAuthError -> UpstreamAuthError``) is the subclass's
    responsibility.
    """

    name: str = "unnamed"

    @abc.abstractmethod
    async def _invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Tool-name-keyed dispatch to the underlying client. Implement me."""
        raise NotImplementedError

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Default call() that delegates to ``_invoke``.

        Subclasses can override for custom behaviour (e.g. adding
        logging, metrics, error wrapping).
        """
        return await self._invoke(tool_name, arguments)

    async def health_check(self) -> bool:
        """Default health check returns True. Override for real probes."""
        return True

    async def close(self) -> None:
        """Default close is a no-op. Override for real cleanup."""
        return None


__all__ = [
    "UpstreamError",
    "UpstreamTimeoutError",
    "UpstreamAuthError",
    "UpstreamNotFoundError",
    "UpstreamUnavailableError",
    "UpstreamClient",
    "BaseUpstream",
]
