"""Dependency-ordered workflow DAG execution with fingerprint caching."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import contextlib


import asyncio
import inspect
import math
import time
from collections.abc import (
    Callable,
    Coroutine,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    Sequence,
)
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, TypeVar

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .hashing import structured_hash

T = TypeVar("T")


class CycleError(ValueError):
    """Raised when a directed graph cycle is detected."""


class WorkflowExecutionError(RuntimeError):
    """Raised when a workflow stage execution fails."""

    def __init__(self,
        message: str,
        *,
        stage_name: str,
        cause: BaseException,
        compensation_errors: Sequence[tuple[str, BaseException]] = (),
    ) -> None:
        super().__init__(message)
        self.stage_name = stage_name
        self.cause = cause
        self.compensation_errors = tuple(compensation_errors)


@dataclass(frozen=True, slots=True)
class WorkflowStage:
    """One named stage in a dependency DAG.

    Parameters
    ----------
    name : str
        Unique stage name.
    run : Callable[[Mapping[str, Any]], Any]
        Stage function receiving completed direct-dependency outputs. May be
        synchronous or an async coroutine function.
    dependencies : tuple[str, ...], optional
        Names of prerequisite stages.
    fingerprint : str | None, optional
        Caller-defined fingerprint for the stage's own configuration/input.
        A stage is cacheable only when it and every transitive dependency have
        fingerprints.
    compensate : Callable[[Any], Any] | None, optional
        Rollback function receiving the stage's own output if a subsequent
        downstream stage fails. May be synchronous or asynchronous.
    """

    name: str
    run: Callable[[Mapping[str, Any]], Any]
    dependencies: tuple[str, ...] = ()
    fingerprint: str | None = None
    compensate: Callable[[Any], Any] | None = None

    def __post_init__(self) -> None:
        """Validate stage identity, callable and dependency declaration."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("stage name must be a non-empty string")
        if not callable(self.run):
            raise TypeError("stage run must be callable")
        if self.compensate is not None and not callable(self.compensate):
            raise TypeError("compensate must be callable or None")

        if isinstance(self.dependencies, (str, bytes, bytearray)):
            raise TypeError(
                f"stage dependencies must be a sequence of strings, not {type(self.dependencies).__name__}"
            )
        try:
            dependencies = tuple(self.dependencies)
        except TypeError as exc:
            raise TypeError(
                f"stage dependencies must be an iterable, got {type(self.dependencies).__name__}"
            ) from exc

        if any(
            not isinstance(item, str) or not item.strip()
            for item in dependencies
        ):
            raise ValueError(
                "stage dependencies must contain non-empty string names"
            )
        if len(set(dependencies)) != len(dependencies):
            raise ValueError("stage dependencies must not contain duplicates")
        if self.name in dependencies:
            raise ValueError("stage cannot depend on itself")

        if self.fingerprint is not None and (
            not isinstance(self.fingerprint, str)
            or not self.fingerprint
        ):
            raise ValueError(
                "fingerprint must be None or a non-empty string"
            )

        object.__setattr__(
            self,
            "dependencies",
            dependencies,
        )


def _validate_rollback_timeout(
    timeout: Any,
) -> float | None:
    """_validate_rollback_timeout() function.

    Parameters
    ----------
    timeout : Any
        timeout parameter.

    Returns
    -------
    float | None
        The result of the operation.
    """
    if timeout is None:
        return None
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError(
            "rollback_timeout must be a finite positive number or None"
        )
    return float(timeout)


class WorkflowDAG:
    """Execute named stages in topological order with safe cache propagation."""

    def __init__(self,
        stages: list[WorkflowStage] | tuple[WorkflowStage, ...],
        *,
        rollback_timeout: float | None = None,
    ) -> None:
        self.rollback_timeout = _validate_rollback_timeout(rollback_timeout)
        try:
            stage_list = list(stages)
        except TypeError as exc:
            raise TypeError("stages must be an iterable of WorkflowStage instances") from exc
        for stage in stage_list:
            if not isinstance(stage, WorkflowStage):
                raise TypeError(
                    f"stages must contain WorkflowStage instances, got {type(stage).__name__}"
                )
        self.stages = {
            stage.name: stage
            for stage in stage_list
        }
        if len(self.stages) != len(stage_list):
            raise ValueError("stage names must be unique")
        if any(not name.strip() for name in self.stages):
            raise ValueError("stage names must be non-empty")
        self._fingerprint_memo: dict[str, str | None] = {}
        self._order = self._topological_order()

    def _topological_order(self) -> tuple[str, ...]:
        """Validate dependencies/cycles and return deterministic execution order.

        Returns
        -------
        tuple[str, ...]
            The result of the operation.
        """
        result: list[str] = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        for start_name in self.stages:
            if start_name in permanent:
                continue
            temporary.add(start_name)
            stack: list[tuple[str, Iterator[str]]] = [
                (start_name, iter(self.stages[start_name].dependencies))
            ]

            while stack:
                name, it = stack[-1]
                try:
                    dependency = next(it)
                except StopIteration:
                    stack.pop()
                    temporary.remove(name)
                    permanent.add(name)
                    result.append(name)
                    continue

                if dependency not in self.stages:
                    raise KeyError(
                        f"missing stage dependency {dependency!r}"
                    )
                if dependency in permanent:
                    continue
                if dependency in temporary:
                    raise ValueError("workflow DAG cycle detected")

                temporary.add(dependency)
                stack.append(
                    (dependency, iter(self.stages[dependency].dependencies))
                )

        return tuple(result)

    def order(self) -> tuple[str, ...]:
        """Return validated topological execution order.

        Returns
        -------
        tuple[str, ...]
            The result of the operation.
        """
        return self._order

    def effective_fingerprint(self,
        name: str,
    ) -> str | None:
        """Return cache fingerprint including all transitive dependencies.

        A stage with no fingerprint, or depending on any un-fingerprinted
        stage, returns None and is therefore deliberately not cacheable.
        """
        if name not in self.stages:
            raise KeyError(name)

        if name in self._fingerprint_memo:
            return self._fingerprint_memo[name]

        memo: dict[str, str | None] = {}
        stack: list[tuple[str, Iterator[str]]] = [
            (name, iter(self.stages[name].dependencies))
        ]
        visited: set[str] = {name}

        while stack:
            stage_name, it = stack[-1]
            if stage_name in self._fingerprint_memo:
                memo[stage_name] = self._fingerprint_memo[stage_name]
                stack.pop()
                continue
            try:
                dependency = next(it)
            except StopIteration:
                stack.pop()
                stage = self.stages[stage_name]
                if stage.fingerprint is None:
                    memo[stage_name] = None
                    self._fingerprint_memo[stage_name] = None
                    continue

                dependencies: dict[str, str] = {}
                any_none = False
                for dep in stage.dependencies:
                    token = memo.get(dep)
                    if token is None:
                        any_none = True
                        break
                    dependencies[dep] = token

                if any_none:
                    memo[stage_name] = None
                    self._fingerprint_memo[stage_name] = None
                else:
                    computed = structured_hash(
                        {
                            "name": stage.name,
                            "fingerprint": stage.fingerprint,
                            "dependency_order": list(stage.dependencies),
                            "dependency_fingerprints": dependencies,
                        }
                    )
                    memo[stage_name] = computed
                    self._fingerprint_memo[stage_name] = computed
                continue

            if dependency in self._fingerprint_memo:
                memo[dependency] = self._fingerprint_memo[dependency]
                continue

            if dependency not in memo and dependency not in visited:
                visited.add(dependency)
                stack.append(
                    (dependency, iter(self.stages[dependency].dependencies))
                )

        res = memo[name]
        self._fingerprint_memo[name] = res
        return res

    def parallel_layers(self) -> tuple[tuple[str, ...], ...]:
        """Group independent stages into topological execution wavefronts.

        Stages in the same layer have no dependencies on each other and can be
        executed concurrently.

        Returns
        -------
        tuple[tuple[str, ...], ...]
            Wavefront layers of stage names.
        """
        layer_map: dict[str, int] = {}
        for name in self._order:
            deps = self.stages[name].dependencies
            if not deps:
                layer_map[name] = 0
            else:
                layer_map[name] = 1 + max(layer_map[dep] for dep in deps)

        num_layers = max(layer_map.values()) + 1 if layer_map else 0
        layers: list[list[str]] = [[] for _ in range(num_layers)]
        for name in self._order:
            layers[layer_map[name]].append(name)
        return tuple(tuple(layer) for layer in layers)

    def dependencies_of(self,
        name: str,
        *,
        transitive: bool = False,
    ) -> tuple[str, ...]:
        """Return stage dependencies in topological execution order.

        Parameters
        ----------
        name : str
            Target stage name.
        transitive : bool, default=False
            If True, return all upstream dependencies recursively; otherwise only direct dependencies.

        Returns
        -------
        tuple[str, ...]
            Dependency stage names in topological order.
        """
        if name not in self.stages:
            raise KeyError(name)
        if not isinstance(transitive, bool):
            raise TypeError("transitive must be bool")
        if not transitive:
            return self.stages[name].dependencies

        collected: set[str] = set()
        stack = list(self.stages[name].dependencies)
        while stack:
            dep = stack.pop()
            if dep not in collected:
                collected.add(dep)
                stack.extend(self.stages[dep].dependencies)
        return tuple(n for n in self._order if n in collected)

    def dependents_of(self,
        name: str,
        *,
        transitive: bool = False,
    ) -> tuple[str, ...]:
        """Return stages depending on this stage in topological execution order.

        Parameters
        ----------
        name : str
            Target stage name.
        transitive : bool, default=False
            If True, return all downstream stages recursively; otherwise only direct dependents.

        Returns
        -------
        tuple[str, ...]
            Dependent stage names in topological order.
        """
        if name not in self.stages:
            raise KeyError(name)
        if not isinstance(transitive, bool):
            raise TypeError("transitive must be bool")
        if not transitive:
            return tuple(
                s_name for s_name in self._order
                if name in self.stages[s_name].dependencies
            )

        downstream: set[str] = set()
        for s_name in self._order:
            if s_name == name:
                continue
            deps = self.stages[s_name].dependencies
            if name in deps or any(d in downstream for d in deps):
                downstream.add(s_name)
        return tuple(n for n in self._order if n in downstream)

    def _rollback_sync(self,
        completed_order: list[str],
        outputs: Mapping[str, Any],
    ) -> list[tuple[str, BaseException]]:
        """Roll back completed stages in reverse execution order synchronously.

        Parameters
        ----------
        completed_order : list[str]
            completed_order parameter.
        outputs : Mapping[str, Any]
            outputs parameter.

        Returns
        -------
        list[tuple[str, BaseException]]
            The result of the operation.
        """
        errors: list[tuple[str, BaseException]] = []
        for name in reversed(completed_order):
            stage = self.stages[name]
            if stage.compensate is not None:
                try:
                    res = stage.compensate(outputs.get(name))
                    if inspect.isawaitable(res):
                        if inspect.iscoroutine(res):
                            res.close()
                        errors.append(
                            (
                                name,
                                TypeError(
                                    f"asynchronous compensation for stage {name!r} "
                                    "cannot be executed during synchronous rollback"
                                ),
                            )
                        )
                except BaseException as exc:
                    errors.append((name, exc))
        return errors

    async def _rollback_async(self,
        completed_order: list[str],
        outputs: Mapping[str, Any],
        *,
        collected_errors: list[tuple[str, BaseException]] | None = None,
    ) -> list[tuple[str, BaseException]]:
        """Roll back completed stages in reverse execution order asynchronously.

        Parameters
        ----------
        completed_order : list[str]
            completed_order parameter.
        outputs : Mapping[str, Any]
            outputs parameter.

        Returns
        -------
        list[tuple[str, BaseException]]
            The result of the operation.
        """
        errors: list[tuple[str, BaseException]] = (
            collected_errors if collected_errors is not None else []
        )
        rev_order = list(reversed(completed_order))
        for idx, name in enumerate(rev_order):
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                for rem_name in rev_order[idx:]:
                    rem_stage = self.stages[rem_name]
                    if rem_stage.compensate is not None:
                        errors.append(
                            (
                                rem_name,
                                asyncio.CancelledError(
                                    f"compensation of stage {rem_name!r} "
                                    "skipped due to cancellation"
                                ),
                            )
                        )
                return errors

            stage = self.stages[name]
            if stage.compensate is not None:
                try:
                    res = stage.compensate(outputs.get(name))
                    if inspect.isawaitable(res):
                        await res
                except asyncio.CancelledError as exc:
                    errors.append((name, exc))
                    for rem_name in rev_order[idx + 1:]:
                        rem_stage = self.stages[rem_name]
                        if rem_stage.compensate is not None:
                            errors.append(
                                (
                                    rem_name,
                                    asyncio.CancelledError(
                                        f"compensation of stage {rem_name!r} "
                                        "skipped due to cancellation"
                                    ),
                                )
                            )
                    return errors
                except BaseException as exc:
                    errors.append((name, exc))
        return errors

    async def _safe_rollback_async(self,
        completed_order: list[str],
        outputs: Mapping[str, Any],
        *,
        timeout: float | None = None,
    ) -> list[tuple[str, BaseException]]:
        """Roll back asynchronously without being detached by outer cancellations.

        Execution is bounded by timeout when configured.
        """
        collected: list[tuple[str, BaseException]] = []
        rollback_task = asyncio.create_task(
            self._rollback_async(
                completed_order, outputs, collected_errors=collected
            )
        )
        effective_timeout = (
            timeout if timeout is not None else self.rollback_timeout
        )
        deadline = (
            time.monotonic() + effective_timeout
            if effective_timeout is not None
            else None
        )

        timed_out = False
        while not rollback_task.done():
            remaining = (
                deadline - time.monotonic()
                if deadline is not None
                else None
            )
            if remaining is not None and remaining <= 0:
                timed_out = True
                rollback_task.cancel()
                break

            try:
                if remaining is not None:
                    await asyncio.wait_for(
                        asyncio.shield(rollback_task), timeout=remaining
                    )
                else:
                    await asyncio.shield(rollback_task)
            except TimeoutError:
                timed_out = True
                rollback_task.cancel()
                break
            except asyncio.CancelledError:
                pass

        if timed_out:
            join_timeout = (
                min(0.05, max(0.005, effective_timeout * 0.5))
                if effective_timeout is not None
                else 0.05
            )
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait([rollback_task], timeout=join_timeout)
            errors: list[tuple[str, BaseException]] = [
                (
                    "rollback_timeout",
                    TimeoutError(
                        f"rollback exceeded timeout of {effective_timeout}s"
                    ),
                )
            ]
            errors.extend(collected)
            if not rollback_task.done():
                errors.append(
                    (
                        "rollback_unfinished",
                        RuntimeError(
                            "rollback task did not terminate within cleanup deadline"
                        ),
                    )
                )
            return errors

        if rollback_task.cancelled():
            res_errors: list[tuple[str, BaseException]] = [
                (
                    "rollback_cancelled",
                    asyncio.CancelledError("rollback was cancelled"),
                )
            ]
            res_errors.extend(collected)
            return res_errors
        try:
            return rollback_task.result()
        except asyncio.CancelledError as exc:
            res_errors = [("rollback_cancelled", exc)]
            res_errors.extend(collected)
            return res_errors
        except BaseException as exc:
            res_errors = [("rollback_error", exc)]
            res_errors.extend(collected)
            return res_errors

    def execute(self,
        *,
        cache: MutableMapping[tuple[str, str], Any] | None = None,
    ) -> dict[str, Any]:
        """Execute all stages and return outputs keyed by stage name.

        Parameters
        ----------
        cache : MutableMapping[tuple[str, str], Any] | None, optional
            Shared cache keyed by stage name and effective fingerprint.

        Returns
        -------
        dict[str, Any]
            Stage outputs in completion/topological order.
        """
        if cache is not None and not isinstance(cache, MutableMapping):
            raise TypeError(f"cache must be a MutableMapping, got {type(cache).__name__}")
        store = cache if cache is not None else {}
        outputs: dict[str, Any] = {}
        executed_order: list[str] = []
        newly_cached: dict[tuple[str, str], Any] = {}

        for name in self._order:
            stage = self.stages[name]
            fingerprint = self.effective_fingerprint(name)
            key = (
                (name, fingerprint)
                if fingerprint is not None
                else None
            )

            if key is not None and key in store:
                outputs[name] = store[key]
                continue

            dependency_outputs = {
                dependency: outputs[dependency]
                for dependency in stage.dependencies
            }
            try:
                output = stage.run(dependency_outputs)
                if inspect.isawaitable(output):
                    if asyncio.iscoroutine(output):
                        output.close()
                    raise TypeError(
                        f"stage {name!r} returned an awaitable in synchronous execute(); "
                        "use async_execute() instead"
                    )
            except BaseException as exc:
                compensation_errors = self._rollback_sync(executed_order, outputs)
                raise WorkflowExecutionError(
                    f"workflow failed at stage {name!r}: {exc}",
                    stage_name=name,
                    cause=exc,
                    compensation_errors=tuple(compensation_errors),
                ) from exc

            outputs[name] = output
            executed_order.append(name)

            if key is not None:
                newly_cached[key] = output

        published_keys: list[tuple[str, str]] = []
        current_key: tuple[str, str] | None = None
        try:
            for k, v in newly_cached.items():
                current_key = k
                store[k] = v
                published_keys.append(k)
                current_key = None
        except BaseException as exc:
            keys_to_clean = list(published_keys)
            if current_key is not None and current_key not in keys_to_clean:
                keys_to_clean.append(current_key)
            for k in keys_to_clean:
                with contextlib.suppress(Exception):
                    del store[k]
            compensation_errors = self._rollback_sync(executed_order, outputs)
            raise WorkflowExecutionError(
                f"workflow cache publication failed: {exc}",
                stage_name="cache_publication",
                cause=exc,
                compensation_errors=tuple(compensation_errors),
            ) from exc

        return outputs

    async def async_execute(self,
        *,
        cache: MutableMapping[tuple[str, str], Any] | None = None,
        concurrency_limit: int | None = None,
        budget: Any = None,
        rollback_timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute stages asynchronously.

        Supports concurrency, budget tracking, and rollback.
        """
        effective_rollback_timeout = (
            _validate_rollback_timeout(rollback_timeout)
            if rollback_timeout is not None
            else self.rollback_timeout
        )
        if concurrency_limit is not None:
            if (
                isinstance(concurrency_limit, bool)
                or not isinstance(concurrency_limit, int)
                or concurrency_limit <= 0
            ):
                raise ValueError("concurrency_limit must be a positive integer or None")

        if cache is not None and not isinstance(cache, MutableMapping):
            raise TypeError(f"cache must be a MutableMapping, got {type(cache).__name__}")

        sem = (
            asyncio.Semaphore(concurrency_limit)
            if concurrency_limit is not None
            else None
        )
        store = cache if cache is not None else {}
        outputs: dict[str, Any] = {}
        executed_order: list[str] = []
        newly_cached: dict[tuple[str, str], Any] = {}
        events: dict[str, asyncio.Event] = {
            name: asyncio.Event() for name in self.stages
        }
        cancel_event = asyncio.Event()
        start_barrier = asyncio.Event()
        failure_box: list[tuple[str, BaseException]] = []
        tasks: list[asyncio.Task[None]] = []

        async def run_stage(
            name: str,
        ) -> None:
            """run_stage() function.

            Parameters
            ----------
            name : str
                name parameter.
            """
            stage = self.stages[name]
            try:
                await start_barrier.wait()
                if cancel_event.is_set():
                    return

                for dep in stage.dependencies:
                    await events[dep].wait()
                    if cancel_event.is_set():
                        return

                if cancel_event.is_set():
                    return

                if budget is not None:
                    if hasattr(budget, "check_deadline"):
                        budget.check_deadline()
                    if hasattr(budget, "consume_steps"):
                        budget.consume_steps(1)

                async with (sem if sem is not None else nullcontext()):
                    if cancel_event.is_set():
                        return

                    fingerprint = self.effective_fingerprint(name)
                    key = (
                        (name, fingerprint)
                        if fingerprint is not None
                        else None
                    )

                    if key is not None and key in store:
                        outputs[name] = store[key]
                        events[name].set()
                        return

                    dependency_outputs = {
                        dep: outputs[dep] for dep in stage.dependencies
                    }
                    res = stage.run(dependency_outputs)
                    if inspect.isawaitable(res):
                        output = await res
                    else:
                        output = res

                    outputs[name] = output
                    executed_order.append(name)
                    if key is not None:
                        newly_cached[key] = output
                    events[name].set()
            except BaseException as exc:
                if not cancel_event.is_set():
                    cancel_event.set()
                    if not isinstance(exc, asyncio.CancelledError):
                        failure_box.append((name, exc))
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                events[name].set()
                raise

        setup_ok = False
        coro: Coroutine[Any, Any, None] | None = None
        try:
            for name in self.stages:
                coro = run_stage(name)
                tasks.append(asyncio.create_task(coro))
                coro = None
            setup_ok = True
        except BaseException:
            if coro is not None:
                coro.close()
            cancel_event.set()
            for t in tasks:
                if not t.done():
                    t.cancel()
            if tasks:
                while True:
                    try:
                        await asyncio.shield(
                            asyncio.gather(*tasks, return_exceptions=True)
                        )
                        break
                    except asyncio.CancelledError:
                        pass
            raise
        finally:
            if setup_ok:
                start_barrier.set()

        caller_cancelled = False
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            caller_cancelled = True
            if not cancel_event.is_set():
                cancel_event.set()
            for t in tasks:
                if not t.done():
                    t.cancel()

            async def _drain() -> list[Any]:
                """_drain() function.

                Returns
                -------
                list[Any]
                    The result of the operation.
                """
                return await asyncio.gather(*tasks, return_exceptions=True)

            drain_task = asyncio.create_task(_drain())
            while not drain_task.done():
                try:
                    await asyncio.shield(drain_task)
                except asyncio.CancelledError:
                    caller_cancelled = True
            results = drain_task.result()

        if failure_box:
            failed_stage, exc = failure_box[0]
            compensation_errors = await self._safe_rollback_async(
                executed_order, outputs, timeout=effective_rollback_timeout
            )
            raise WorkflowExecutionError(
                f"async workflow failed at stage {failed_stage!r}: {exc}",
                stage_name=failed_stage,
                cause=exc,
                compensation_errors=tuple(compensation_errors),
            ) from exc

        for res in results:
            if isinstance(res, BaseException) and not isinstance(
                res, asyncio.CancelledError
            ):
                compensation_errors = await self._safe_rollback_async(
                    executed_order, outputs, timeout=effective_rollback_timeout
                )
                raise WorkflowExecutionError(
                    f"async workflow failed: {res}",
                    stage_name="unknown",
                    cause=res,
                    compensation_errors=tuple(compensation_errors),
                ) from res

        cancelled = caller_cancelled or any(
            isinstance(res, asyncio.CancelledError) for res in results
        )
        if cancelled:
            await self._safe_rollback_async(
                executed_order, outputs, timeout=effective_rollback_timeout
            )
            raise asyncio.CancelledError()

        published_keys: list[tuple[str, str]] = []
        current_key: tuple[str, str] | None = None
        try:
            for k, v in newly_cached.items():
                current_key = k
                store[k] = v
                published_keys.append(k)
                current_key = None
        except BaseException as exc:
            keys_to_clean = list(published_keys)
            if current_key is not None and current_key not in keys_to_clean:
                keys_to_clean.append(current_key)
            for k in keys_to_clean:
                with contextlib.suppress(Exception):
                    del store[k]
            compensation_errors = await self._safe_rollback_async(
                executed_order, outputs, timeout=effective_rollback_timeout
            )
            raise WorkflowExecutionError(
                f"async workflow cache publication failed: {exc}",
                stage_name="cache_publication",
                cause=exc,
                compensation_errors=tuple(compensation_errors),
            ) from exc

        return outputs


def _normalize_graph(
    graph: Mapping[T, Iterable[T]],
) -> dict[T, set[T]]:
    adj: dict[T, set[T]] = {k: set(v) for k, v in graph.items()}
    #? Ensure all referenced target nodes exist in adj
    for targets in list(adj.values()):
        for node in targets:
            if node not in adj:
                adj[node] = set()
    return adj


def add_edge(
    graph: dict[T, set[T]],
    u: T,
    v: T,
) -> None:
    """Add a directed edge u -> v to an adjacency dictionary."""
    if u not in graph:
        graph[u] = set()
    if v not in graph:
        graph[v] = set()
    graph[u].add(v)


def detect_cycles(
    graph: Mapping[T, Iterable[T]],
) -> list[list[T]]:
    """Detect cycles in a directed graph using depth-first search.

    Returns a list of cycles, each represented as a list of nodes.
    """
    adj = _normalize_graph(graph)
    visited: dict[T, int] = {}  #? 0: visiting, 1: visited
    stack: list[T] = []
    cycles: list[list[T]] = []

    def dfs(
        node: T,
    ) -> None:
        visited[node] = 0
        stack.append(node)
        for nxt in adj.get(node, ()):
            state = visited.get(nxt)
            if state == 0:
                #? Cycle found
                idx = stack.index(nxt)
                cycles.append(stack[idx:] + [nxt])
            elif state is None:
                dfs(nxt)
        stack.pop()
        visited[node] = 1

    for n in adj:
        if n not in visited:
            dfs(n)
    return cycles


def is_dag(
    graph: Mapping[T, Iterable[T]],
) -> bool:
    """Return True if graph is a directed acyclic graph (has no cycles)."""
    return len(detect_cycles(graph)) == 0


def topological_sort(
    graph: Mapping[T, Iterable[T]],
) -> list[T]:
    """Return a topological sort of nodes in a directed acyclic graph.

    Raises
    ------
    CycleError
        If the graph contains at least one cycle.
    """
    adj = _normalize_graph(graph)
    in_degree: dict[T, int] = {k: 0 for k in adj}
    for targets in adj.values():
        for t in targets:
            in_degree[t] = in_degree.get(t, 0) + 1

    ready = [k for k, deg in in_degree.items() if deg == 0]
    result: list[T] = []

    while ready:
        node = ready.pop()
        result.append(node)
        for nxt in adj.get(node, ()):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                ready.append(nxt)

    if len(result) != len(adj):
        cycles = detect_cycles(graph)
        raise CycleError(f"graph contains cycles: {cycles}")
    return result


def parallel_levels(
    graph: Mapping[T, Iterable[T]],
) -> list[set[T]]:
    """Partition DAG nodes into execution levels that can run in parallel."""
    adj = _normalize_graph(graph)
    in_degree: dict[T, int] = {k: 0 for k in adj}
    for targets in adj.values():
        for t in targets:
            in_degree[t] = in_degree.get(t, 0) + 1

    current = {k for k, deg in in_degree.items() if deg == 0}
    levels: list[set[T]] = []
    processed = 0

    while current:
        levels.append(current)
        processed += len(current)
        next_level: set[T] = set()
        for node in current:
            for nxt in adj.get(node, ()):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    next_level.add(nxt)
        current = next_level

    if processed != len(adj):
        raise CycleError("cannot group cyclic graph into parallel levels")
    return levels


def descendants(
    graph: Mapping[T, Iterable[T]],
    node: T,
) -> set[T]:
    """Return all downstream nodes reachable from `node`."""
    adj = _normalize_graph(graph)
    visited: set[T] = set()
    queue = list(adj.get(node, ()))
    while queue:
        curr = queue.pop()
        if curr not in visited:
            visited.add(curr)
            queue.extend(adj.get(curr, ()))
    return visited


def ancestors(
    graph: Mapping[T, Iterable[T]],
    node: T,
) -> set[T]:
    """Return all upstream nodes that can reach `node`."""
    adj = _normalize_graph(graph)
    #? Reverse graph
    rev: dict[T, set[T]] = {k: set() for k in adj}
    for u, targets in adj.items():
        for v in targets:
            rev[v].add(u)

    visited: set[T] = set()
    queue = list(rev.get(node, ()))
    while queue:
        curr = queue.pop()
        if curr not in visited:
            visited.add(curr)
            queue.extend(rev.get(curr, ()))
    return visited


def has_path(
    graph: Mapping[T, Iterable[T]],
    source: T,
    target: T,
) -> bool:
    """Return True if a directed path exists from source to target."""
    if source == target:
        return True
    return target in descendants(graph, source)


def subgraph(
    graph: Mapping[T, Iterable[T]],
    nodes: Iterable[T],
) -> dict[T, set[T]]:
    """Return the induced subgraph containing only specified nodes."""
    allowed = set(nodes)
    adj = _normalize_graph(graph)
    return {
        u: {v for v in targets if v in allowed}
        for u, targets in adj.items()
        if u in allowed
    }


def transitive_reduction(
    graph: Mapping[T, Iterable[T]],
) -> dict[T, set[T]]:
    """Compute the transitive reduction of a DAG."""
    topo = topological_sort(graph)
    adj = _normalize_graph(graph)
    reduction: dict[T, set[T]] = {u: set(adj.get(u, ())) for u in topo}

    for u in topo:
        targets = list(reduction[u])
        for v in targets:
            for w in reduction[u]:
                if w != v and has_path(reduction, w, v):
                    reduction[u].discard(v)
                    break
    return reduction


def critical_path(
    graph: Mapping[T, Iterable[T]],
    weights: Mapping[T, float],
) -> tuple[list[T], float]:
    """Compute the longest path through a DAG and its cumulative weight.

    Parameters
    ----------
    graph : Mapping[T, Iterable[T]]
        Directed acyclic graph.
    weights : Mapping[T, float]
        Cost or execution duration for each node.

    Returns
    -------
    tuple[list[T], float]
        (path_as_list_of_nodes, total_path_weight)
    """
    topo = topological_sort(graph)
    if not topo:
        return ([], 0.0)

    dist: dict[T, float] = {u: float(weights.get(u, 0.0)) for u in topo}
    prev: dict[T, T | None] = {u: None for u in topo}

    adj = _normalize_graph(graph)

    for u in topo:
        u_dist = dist[u]
        for v in adj.get(u, ()):
            v_weight = float(weights.get(v, 0.0))
            if u_dist + v_weight > dist[v]:
                dist[v] = u_dist + v_weight
                prev[v] = u

    #? Find node with maximum distance
    end_node = max(topo, key=lambda n: dist[n])
    max_weight = dist[end_node]

    #? Reconstruct path
    path: list[T] = []
    curr: T | None = end_node
    while curr is not None:
        path.append(curr)
        curr = prev[curr]
    path.reverse()

    return path, max_weight


__all__ = [
    "CycleError",
    "WorkflowDAG",
    "WorkflowExecutionError",
    "WorkflowStage",
    "add_edge",
    "ancestors",
    "critical_path",
    "descendants",
    "detect_cycles",
    "has_path",
    "is_dag",
    "parallel_levels",
    "subgraph",
    "topological_sort",
    "transitive_reduction",
]
