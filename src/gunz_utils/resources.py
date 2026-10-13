"""Deterministic sync/async resource ownership groups."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack
from types import TracebackType
from typing import Any


class ResourceGroup:
    def __init__(self) -> None:
        self._stack = ExitStack()
        self._entered = False

    def __enter__(self) -> ResourceGroup:
        self._stack.__enter__()
        self._entered = True
        return self

    def enter(self,
        resource: Any,
    ) -> Any:
        """enter() function.

        Parameters
        ----------
        resource : Any
            resource parameter.

        Returns
        -------
        Any
            The result of the operation.

        Raises
        ------
        RuntimeError
            If the group's context manager was not entered, so a resource is
            not silently pushed onto a stack that can never release it.
        """
        if not self._entered:
            raise RuntimeError("resource group must be entered before use")
        return self._stack.enter_context(resource)

    def __exit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        result = self._stack.__exit__(exc_type, exc_value, traceback)
        #? Reset the entered state so a later enter() (after the context has
        #? exited) raises instead of pushing onto a stack that can never
        #? release the resource.
        self._entered = False
        return result


class AsyncResourceGroup:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._entered = False

    async def __aenter__(self) -> AsyncResourceGroup:
        await self._stack.__aenter__()
        self._entered = True
        return self

    async def enter(self,
        resource: Any,
    ) -> Any:
        """enter() function.

        Parameters
        ----------
        resource : Any
            resource parameter.

        Returns
        -------
        Any
            The result of the operation.

        Raises
        ------
        RuntimeError
            If the group's context manager was not entered, so a resource is
            not silently pushed onto a stack that can never release it.
        """
        if not self._entered:
            raise RuntimeError("resource group must be entered before use")
        return await self._stack.enter_async_context(resource)

    async def __aexit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        result = await self._stack.__aexit__(exc_type, exc_value, traceback)
        #? Reset the entered state so a later enter() (after the context has
        #? exited) raises instead of pushing onto a stack that can never
        #? release the resource.
        self._entered = False
        return result


__all__ = ["AsyncResourceGroup", "ResourceGroup"]
