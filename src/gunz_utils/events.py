"""Pub-sub event bus, observer patterns, debounce, and throttle decorators."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import functools
import inspect
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class EventBus:
    """Thread-safe and async-compatible publish-subscribe event bus."""

    def __init__(self,
        *,
        on_error: Callable[[Exception, str], None] | None = None,
    ) -> None:
        self.on_error = on_error
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._once_subscribers: dict[str, set[Callable[..., Any]]] = defaultdict(set)

    def subscribe(self,
        topic: str,
        handler: Callable[..., Any],
    ) -> Callable[[], None]:
        """Register a callback for the specified topic. Returns an unsubscribe callable.
        """
        if not isinstance(topic, str) or not topic:
            raise ValueError("topic must be a non-empty string")
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._lock:
            self._subscribers[topic].append(handler)

        def unsubscribe() -> None:
            self.unsubscribe(topic, handler)

        return unsubscribe

    def subscribe_once(self,
        topic: str,
        handler: Callable[..., Any],
    ) -> Callable[[], None]:
        """Register a one-time callback auto-removed after its first trigger."""
        if not isinstance(topic, str) or not topic:
            raise ValueError("topic must be a non-empty string")
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._lock:
            self._subscribers[topic].append(handler)
            self._once_subscribers[topic].add(handler)

        def unsubscribe() -> None:
            self.unsubscribe(topic, handler)

        return unsubscribe

    def unsubscribe(self,
        topic: str,
        handler: Callable[..., Any],
    ) -> bool:
        """Unregister a callback from the specified topic."""
        with self._lock:
            subs = self._subscribers.get(topic)
            if subs and handler in subs:
                subs.remove(handler)
                self._once_subscribers[topic].discard(handler)
                return True
            return False

    def publish(self,
        topic: str,
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Synchronously dispatch event to all subscribers of topic."""
        with self._lock:
            handlers = list(self._subscribers.get(topic, ()))
            onces = set(self._once_subscribers.get(topic, ()))
            #? Clean up once handlers
            if onces:
                self._subscribers[topic] = [
    h for h in self._subscribers[topic] if h not in onces]
                self._once_subscribers[topic].clear()

        results: list[Any] = []
        for handler in handlers:
            try:
                res = handler(*args, **kwargs)
                results.append(res)
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(exc, topic)
                else:
                    raise
        return results

    async def publish_async(self,
        topic: str,
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Asynchronously dispatch event to all subscribers, awaiting coroutines."""
        with self._lock:
            handlers = list(self._subscribers.get(topic, ()))
            onces = set(self._once_subscribers.get(topic, ()))
            if onces:
                self._subscribers[topic] = [
    h for h in self._subscribers[topic] if h not in onces]
                self._once_subscribers[topic].clear()

        results: list[Any] = []
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    res = await handler(*args, **kwargs)
                else:
                    res = handler(*args, **kwargs)
                    if inspect.isawaitable(res):
                        res = await res
                results.append(res)
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(exc, topic)
                else:
                    raise
        return results


def debounce(
    seconds: float,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Delay execution until `seconds` elapsed since last call."""
    if isinstance(
    seconds, bool) or not isinstance(
        seconds, (int, float)) or seconds < 0:
        raise ValueError("seconds must be a non-negative number")

    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        timer: threading.Timer | None = None
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> None:
            nonlocal timer
            with lock:
                if timer is not None:
                    timer.cancel()
                timer = threading.Timer(seconds, func, args, kwargs)
                timer.daemon = True
                timer.start()

        def cancel() -> None:
            nonlocal timer
            with lock:
                if timer is not None:
                    timer.cancel()
                    timer = None

        wrapper.cancel = cancel  # type: ignore[attr-defined]
        return wrapper

    return decorator


def throttle(
    seconds: float,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Limit execution frequency to at most once per `seconds`."""
    if isinstance(
    seconds, bool) or not isinstance(
        seconds, (int, float)) or seconds < 0:
        raise ValueError("seconds must be a non-negative number")

    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        last_called = 0.0
        lock = threading.Lock()
        last_result: Any = None

        @functools.wraps(func)
        def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            nonlocal last_called, last_result
            with lock:
                now = time.monotonic()
                if now - last_called >= seconds:
                    last_called = now
                    last_result = func(*args, **kwargs)
                return last_result

        return wrapper

    return decorator


class AsyncEvent:
    """Asyncio Event wrapper with wait_with_timeout support."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def is_set(self) -> bool:
        """Return True if the internal flag is true."""
        return self._event.is_set()

    def set(self) -> None:
        """Set the internal flag to true."""
        self._event.set()

    def clear(self) -> None:
        """Reset the internal flag to false."""
        self._event.clear()

    async def wait(self) -> bool:
        """Block until the internal flag is true."""
        return await self._event.wait()

    async def wait_with_timeout(self,
        timeout: float | None = None,
    ) -> bool:
        """Block until flag is true or timeout expires. Returns True if flag set."""
        if timeout is None:
            await self._event.wait()
            return True
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False


class SignalObserver(Generic[T]):
    """State observer notifying subscribers upon value transitions."""

    def __init__(self,
        initial_value: T,
    ) -> None:
        self._value = initial_value
        self._listeners: list[Callable[[T, T], Any]] = []

    @property
    def value(self) -> T:
        """Return the current observed value."""
        return self._value

    @value.setter
    def value(self,
        new_value: T,
    ) -> None:
        """Set a new value and notify listeners if changed."""
        old_value = self._value
        if old_value != new_value:
            self._value = new_value
            for listener in list(self._listeners):
                listener(old_value, new_value)

    def subscribe(self,
        listener: Callable[[T, T], Any],
    ) -> Callable[[], None]:
        """Subscribe to value changes with listener(old_value, new_value)."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe


__all__ = [
    "AsyncEvent",
    "EventBus",
    "SignalObserver",
    "debounce",
    "throttle",
]
