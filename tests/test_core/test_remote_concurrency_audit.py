"""Finite independent process allocation, replay and cache generation proofs."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
# isort: split

from __future__ import annotations

import asyncio
import multiprocessing
import sys
from pathlib import Path
from typing import Any, cast

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
# isort: split

import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
# isort: split

import gunz_utils.concurrency as concurrency
from gunz_utils.cache import async_ttl_cache


def _record_once(
    item: tuple[str, int],
) -> int:
    directory, number = item
    with (Path(directory) / str(number)).open("a") as stream:
        stream.write("called\n")
    if number == 1:
        raise RuntimeError("finite worker failure")
    return number


def test_auto_workers_do_not_exceed_finite_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allocations: list[int] = []

    class Executor:
        def __init__(self,
            *,
            max_workers: int,
        ) -> None:
            allocations.append(max_workers)

        def __enter__(self) -> Executor:
            return self

        def __exit__(self,
            *args: Any,
        ) -> None:
            pass

        def map(self,
            func: Any,
            items: Any,
            *,
            chunksize: int,
        ) -> Any:
            return map(func, items)

    monkeypatch.setattr(concurrency.os, "cpu_count", lambda: 128)
    monkeypatch.setattr(concurrency.concurrent.futures, "ProcessPoolExecutor", Executor)
    assert list(concurrency.process_imap(abs, range(-9, 0))) == list(range(9, 0, -1))
    assert allocations == [9]


@pytest.mark.parametrize("threshold", [sys.maxsize, sys.maxsize + 1])
def test_large_valid_threshold_accepts_empty_input(
    threshold: int,
) -> None:
    assert list(concurrency.process_imap(abs, [], threshold=threshold)) == []


@pytest.mark.parametrize("threshold", [-1, True, 1.5])
def test_map_validates_threshold_before_consuming(
    threshold: Any,
) -> None:
    effects: list[str] = []

    def items() -> Any:
        effects.append("consumed")
        yield 1

    with pytest.raises(ValueError, match="threshold"):
        concurrency.process_map(abs, items(), threshold=threshold)
    assert effects == []


@pytest.mark.parametrize("mapper", [concurrency.process_map, concurrency.process_imap])
def test_real_worker_failure_never_replays_completed_work(
    tmp_path: Path,
    mapper: Any,
) -> None:
    with pytest.raises(RuntimeError, match="finite worker failure"):
        list(
            mapper(
                _record_once,
                [(str(tmp_path), n) for n in range(2)],
                workers=2,
                threshold=0,
                fallback_serial=True,
            )
        )
    assert [tmp_path.joinpath(str(n)).read_text() for n in range(2)] == [
        "called\n"
    ] * 2
    assert not any(child.is_alive() for child in multiprocessing.active_children())


def test_clear_detaches_old_generation_and_cancelled_waiter() -> None:
    async def proof() -> None:
        started = [asyncio.Event(), asyncio.Event()]
        release = [asyncio.Event(), asyncio.Event()]
        calls = 0

        @async_ttl_cache(ttl=10)
        async def value() -> int:
            nonlocal calls
            index = calls
            calls += 1
            started[index].set()
            await release[index].wait()
            return index

        old = asyncio.create_task(value())
        await asyncio.wait_for(started[0].wait(), 1)
        await value.cache_clear()
        fresh = asyncio.create_task(value())
        await asyncio.wait_for(started[1].wait(), 1)
        old.cancel()
        with pytest.raises(asyncio.CancelledError):
            await old
        release[0].set()
        await asyncio.sleep(0)
        release[1].set()
        assert await asyncio.wait_for(fresh, 1) == 1
        assert await value() == 1
        assert calls == 2

    asyncio.run(proof())


@pytest.mark.parametrize("kind", ["cache", "singleflight"])
def test_pending_async_producer_requires_one_live_event_loop(
    kind: str,
) -> None:
    import threading

    from gunz_utils.cache import SingleFlight

    ready = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    async def factory() -> int:
        ready.set()
        while not release.is_set():
            await asyncio.sleep(0.001)
        return 7

    if kind == "cache":
        cached = async_ttl_cache(ttl=10)(factory)

        async def call() -> int:
            return await cached()
    else:
        flight = SingleFlight()

        async def call() -> int:
            return await flight.run("shared", factory)

    def holder() -> None:
        try:
            assert asyncio.run(call()) == 7
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=holder)
    thread.start()
    try:
        assert ready.wait(1), "producer did not reach its finite release barrier"
        with pytest.raises(RuntimeError, match="different loop"):
            asyncio.run(call())
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert errors == []


@pytest.mark.parametrize("mapper", ["process_map", "process_imap"])
def test_abrupt_worker_death_propagates_without_serial_replay(
    tmp_path: Path,
    mapper: str,
) -> None:
    import os
    import subprocess
    import textwrap

    script = tmp_path / "finite_worker_death.py"
    script.write_text(
        textwrap.dedent("""\
        import os
        import sys
        import time
        from pathlib import Path
        from concurrent.futures.process import BrokenProcessPool
        from gunz_utils.concurrency import process_map, process_imap

        def work(item):
            directory, number = item
            directory = Path(directory)
            if number == 1:
                deadline = time.monotonic() + 2
                while not (directory / '0').exists():
                    if time.monotonic() > deadline:
                        raise RuntimeError('peer did not acknowledge finite work')
                    time.sleep(0.001)
            with (directory / str(number)).open('a') as stream:
                stream.write('called\\n')
            if number == 1:
                os._exit(23)
            return number

        if __name__ == '__main__':
            mapper = globals()[sys.argv[1]]
            try:
                list(mapper(work, [(sys.argv[2], n) for n in range(2)],
                            workers=2, threshold=0, fallback_serial=True))
            except BrokenProcessPool:
                print('worker-death-propagated', flush=True)
            else:
                raise RuntimeError('worker failure did not propagate')
        """)
    )
    result = subprocess.run(
        [sys.executable, str(script), mapper, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=6,
        env={**os.environ, "PYTHONPATH": str(Path(concurrency.__file__).parent.parent)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "worker-death-propagated"
    assert [tmp_path.joinpath(str(n)).read_text() for n in range(2)] == [
        "called\n"
    ] * 2


def test_input_failure_after_prefix_propagates_before_window_execution(
    tmp_path: Path,
) -> None:
    def source() -> Any:
        yield (str(tmp_path), 0)
        raise RuntimeError("finite input failure")

    with pytest.raises(RuntimeError, match="finite input failure"):
        list(concurrency.process_imap(_record_once, source(), workers=2, threshold=0))
    assert list(tmp_path.iterdir()) == []


class _MultiprocessingCallable:
    def __reduce__(self) -> Any:
        raise TypeError("plain encoding deliberately unsupported")

    def __call__(self,
        value: int,
    ) -> tuple[int, int]:
        import os

        return os.getpid(), value


def _make_multiprocessing_callable() -> _MultiprocessingCallable:
    return _MultiprocessingCallable()


def _reduce_multiprocessing_callable(
    _value: _MultiprocessingCallable,
) -> Any:
    return _make_multiprocessing_callable, ()


@pytest.mark.parametrize("mapper", [concurrency.process_map, concurrency.process_imap])
def test_preflight_uses_multiprocessing_registered_reducers(
    monkeypatch: pytest.MonkeyPatch,
    mapper: Any,
) -> None:
    import os
    from multiprocessing.reduction import ForkingPickler

    monkeypatch.setitem(
        cast(Any, ForkingPickler)._extra_reducers,
        _MultiprocessingCallable,
        _reduce_multiprocessing_callable,
    )
    results = list(mapper(_MultiprocessingCallable(), [7, 8], workers=2, threshold=0))
    assert [value for _pid, value in results] == [7, 8]
    assert all(pid != os.getpid() for pid, _value in results)


@pytest.mark.parametrize("mapper", [concurrency.process_map, concurrency.process_imap])
@pytest.mark.parametrize(
    "error_type",
    [
        MemoryError,
        OSError,
        RecursionError,
        RuntimeError,
        KeyboardInterrupt,
        asyncio.CancelledError,
    ],
)
def test_preflight_resource_and_signal_failures_never_execute_serially(
    monkeypatch: pytest.MonkeyPatch,
    mapper: Any,
    error_type: Any,
) -> None:
    from multiprocessing.reduction import ForkingPickler

    failure = error_type("finite preflight failure")
    effects: list[int] = []

    def encode(
        _value: Any,
    ) -> Any:
        raise failure

    def work(
        value: int,
    ) -> int:
        effects.append(value)
        return value

    monkeypatch.setattr(ForkingPickler, "dumps", encode)
    with pytest.raises(error_type) as caught:
        list(mapper(work, [1, 2], workers=2, threshold=0))
    assert caught.value is failure
    assert effects == []


@pytest.mark.parametrize("mapper", [concurrency.process_map, concurrency.process_imap])
@pytest.mark.parametrize("error_name", ["PicklingError", "AttributeError", "TypeError"])
def test_preflight_only_documented_encoding_failures_fallback(
    monkeypatch: pytest.MonkeyPatch,
    mapper: Any,
    error_name: str,
) -> None:
    from _pickle import PicklingError
    from multiprocessing.reduction import ForkingPickler

    error_type = {
        "PicklingError": PicklingError,
        "AttributeError": AttributeError,
        "TypeError": TypeError,
    }[error_name]
    effects: list[int] = []

    def encode(
        _value: Any,
    ) -> Any:
        raise error_type("finite encoding rejection")

    def work(
        value: int,
    ) -> int:
        effects.append(value)
        return value * 2

    monkeypatch.setattr(ForkingPickler, "dumps", encode)
    assert list(mapper(work, [1, 2], workers=2, threshold=0)) == [2, 4]
    assert effects == [1, 2]


def test_preflight_imports_exception_only_without_deserialization() -> None:
    import ast

    tree = ast.parse(Path(concurrency.__file__).read_text())
    exception_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] != "pickle" for alias in node.names)
            assert all(alias.name != "_pickle" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "pickle"
            if node.module == "_pickle":
                exception_imports.extend(alias.name for alias in node.names)
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"load", "loads", "Unpickler"}
        if isinstance(node, ast.Name):
            assert node.id not in {"load", "loads", "Unpickler"}
    assert exception_imports == ["PicklingError"]
