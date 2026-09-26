"""Small testing helpers with no test-framework dependency."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager


@contextmanager
def temporary_env(
    values: Mapping[str, str | None],
) -> Iterator[None]:
    """Temporarily set or remove environment variables and restore them."""
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def eventually(
    predicate: Callable[[], bool],
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> None:
    """Wait until a predicate succeeds or raise TimeoutError."""
    if timeout < 0 or interval <= 0:
        raise ValueError("timeout must be non-negative and interval positive")
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("condition did not become true before timeout")
        time.sleep(interval)


__all__ = ["eventually", "temporary_env"]
