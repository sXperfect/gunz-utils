"""Deterministic sync/async resource ownership groups."""

from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack
from typing import Any


class ResourceGroup:
    def __init__(self) -> None:
        self._stack = ExitStack()

    def __enter__(self) -> ResourceGroup:
        self._stack.__enter__()
        return self

    def enter(self, resource: Any) -> Any:
        return self._stack.enter_context(resource)

    def __exit__(self, *exc: object) -> bool | None:
        return self._stack.__exit__(*exc)


class AsyncResourceGroup:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> AsyncResourceGroup:
        await self._stack.__aenter__()
        return self

    async def enter(self, resource: Any) -> Any:
        return await self._stack.enter_async_context(resource)

    async def __aexit__(self, *exc: object) -> bool | None:
        return await self._stack.__aexit__(*exc)


__all__ = ["AsyncResourceGroup", "ResourceGroup"]
