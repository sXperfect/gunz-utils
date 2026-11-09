"""Deterministic sync/async resource ownership groups."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from contextlib import AsyncExitStack, ExitStack
from types import TracebackType
from typing import Any


class ResourceGroup:
    """Synchronous resource group managing multiple nested context managers and callbacks."""

    def __init__(self) -> None:
        self._stack = ExitStack()

    def __enter__(self) -> ResourceGroup:
        self._stack.__enter__()
        return self

    def enter(self,
        resource: Any,
    ) -> Any:
        """Enter a context manager and register its exit callback.

        Parameters
        ----------
        resource : Any
            Context manager to enter.

        Returns
        -------
        Any
            Value returned by entering the context manager.
        """
        return self._stack.enter_context(resource)

    def callback(self,
        callback: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        """Register an arbitrary cleanup callback.

        Parameters
        ----------
        callback : Callable[..., Any]
            Function to call on exit.
        args : Any
            Positional arguments for callback.
        kwargs : Any
            Keyword arguments for callback.

        Returns
        -------
        Callable[..., Any]
            The registered callback.
        """
        return self._stack.callback(callback, *args, **kwargs)

    def close(self) -> None:
        """Close the resource group and unwind all registered exits."""
        self._stack.close()

    def __exit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return self._stack.__exit__(exc_type, exc_value, traceback)


class AsyncResourceGroup:
    """Asynchronous resource group managing nested async context managers and cleanup callbacks."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> AsyncResourceGroup:
        await self._stack.__aenter__()
        return self

    async def enter(self,
        resource: Any,
    ) -> Any:
        """Enter an async context manager and register its exit callback.

        Parameters
        ----------
        resource : Any
            Async context manager to enter.

        Returns
        -------
        Any
            Value returned by entering the async context manager.
        """
        return await self._stack.enter_async_context(resource)

    def callback(self,
        callback: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Callable[..., Any]:
        """Register an arbitrary sync or async cleanup callback.

        Parameters
        ----------
        callback : Callable[..., Any]
            Function to call on exit.
        args : Any
            Positional arguments for callback.
        kwargs : Any
            Keyword arguments for callback.

        Returns
        -------
        Callable[..., Any]
            The registered callback.
        """
        return self._stack.callback(callback, *args, **kwargs)

    async def aclose(self) -> None:
        """Close the async resource group and unwind all registered exits."""
        await self._stack.aclose()

    async def __aexit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return await self._stack.__aexit__(exc_type, exc_value, traceback)


__all__ = ["AsyncResourceGroup", "ResourceGroup"]
