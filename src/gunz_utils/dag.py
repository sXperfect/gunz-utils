"""Dependency-ordered workflow DAG execution with fingerprint caching."""

from __future__ import annotations

import asyncio
import inspect
import math
import time
from collections.abc import Callable, Coroutine, Mapping, MutableMapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from .hashing import structured_hash


class WorkflowExecutionError(RuntimeError):
    """Raised when a workflow stage execution fails."""

    def __init__(
        self,
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


@dataclass(frozen=True)
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
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("stage name must be a non-empty string")
        if not callable(self.run):
            raise TypeError("stage run must be callable")
        if self.compensate is not None and not callable(self.compensate):
            raise TypeError("compensate must be callable or None")

        dependencies = tuple(self.dependencies)
        if any(
            not isinstance(item, str) or not item
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


def _validate_rollback_timeout(timeout: Any) -> float | None:
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

    def __init__(
        self,
        stages: list[WorkflowStage] | tuple[WorkflowStage, ...],
        *,
        rollback_timeout: float | None = None,
    ) -> None:
        self.rollback_timeout = _validate_rollback_timeout(rollback_timeout)
        stage_list = list(stages)
        self.stages = {
            stage.name: stage
            for stage in stage_list
        }
        if len(self.stages) != len(stage_list):
            raise ValueError("stage names must be unique")
        if any(not name for name in self.stages):
            raise ValueError("stage names must be non-empty")
        self._order = self._topological_order()

    def _topological_order(self) -> tuple[str, ...]:
        """Validate dependencies/cycles and return deterministic execution order."""
        result: list[str] = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(name: str) -> None:
            if name in permanent:
                return
            if name in temporary:
                raise ValueError("workflow DAG cycle detected")

            stage = self.stages[name]
            temporary.add(name)
            for dependency in stage.dependencies:
                if dependency not in self.stages:
                    raise KeyError(
                        f"missing stage dependency {dependency!r}"
                    )
                visit(dependency)
            temporary.remove(name)
            permanent.add(name)
            result.append(name)

        for name in self.stages:
            visit(name)
        return tuple(result)

    def order(self) -> tuple[str, ...]:
        """Return validated topological execution order."""
        return self._order

    def effective_fingerprint(
        self,
        name: str,
    ) -> str | None:
        """Return cache fingerprint including all transitive dependencies.

        A stage with no fingerprint, or depending on any un-fingerprinted
        stage, returns None and is therefore deliberately not cacheable.
        """
        if name not in self.stages:
            raise KeyError(name)

        memo: dict[str, str | None] = {}

        def resolve(stage_name: str) -> str | None:
            if stage_name in memo:
                return memo[stage_name]

            stage = self.stages[stage_name]
            if stage.fingerprint is None:
                memo[stage_name] = None
                return None

            dependencies: dict[str, str] = {}
            for dependency in stage.dependencies:
                token = resolve(dependency)
                if token is None:
                    memo[stage_name] = None
                    return None
                dependencies[dependency] = token

            token = structured_hash(
                {
                    "name": stage.name,
                    "fingerprint": stage.fingerprint,
                    "dependency_order": list(stage.dependencies),
                    "dependency_fingerprints": dependencies,
                }
            )
            memo[stage_name] = token
            return token

        return resolve(name)

    def _rollback_sync(
        self,
        completed_order: list[str],
        outputs: Mapping[str, Any],
    ) -> list[tuple[str, BaseException]]:
        """Roll back completed stages in reverse execution order synchronously."""
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

    async def _rollback_async(
        self,
        completed_order: list[str],
        outputs: Mapping[str, Any],
    ) -> list[tuple[str, BaseException]]:
        """Roll back completed stages in reverse execution order asynchronously."""
        errors: list[tuple[str, BaseException]] = []
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

    async def _safe_rollback_async(
        self,
        completed_order: list[str],
        outputs: Mapping[str, Any],
        *,
        timeout: float | None = None,
    ) -> list[tuple[str, BaseException]]:
        """Roll back asynchronously without being detached by outer cancellations.

        Execution is bounded by timeout when configured.
        """
        rollback_task = asyncio.create_task(
            self._rollback_async(completed_order, outputs)
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
            try:
                await asyncio.wait([rollback_task], timeout=join_timeout)
            except asyncio.CancelledError:
                pass
            errors: list[tuple[str, BaseException]] = [
                (
                    "rollback_timeout",
                    TimeoutError(
                        f"rollback exceeded timeout of {effective_timeout}s"
                    ),
                )
            ]
            if rollback_task.done() and not rollback_task.cancelled():
                try:
                    res = rollback_task.result()
                    if isinstance(res, list):
                        errors.extend(res)
                except Exception:
                    pass
            elif not rollback_task.done():
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
            return [
                (
                    "rollback_cancelled",
                    asyncio.CancelledError("rollback was cancelled"),
                )
            ]
        try:
            return rollback_task.result()
        except asyncio.CancelledError as exc:
            return [("rollback_cancelled", exc)]
        except BaseException as exc:
            return [("rollback_error", exc)]

    def execute(
        self,
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
                try:
                    del store[k]
                except Exception:
                    pass
            compensation_errors = self._rollback_sync(executed_order, outputs)
            raise WorkflowExecutionError(
                f"workflow cache publication failed: {exc}",
                stage_name="cache_publication",
                cause=exc,
                compensation_errors=tuple(compensation_errors),
            ) from exc

        return outputs

    async def async_execute(
        self,
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

        async def run_stage(name: str) -> None:
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
        except BaseException as exc:
            keys_to_clean = list(published_keys)
            if current_key is not None and current_key not in keys_to_clean:
                keys_to_clean.append(current_key)
            for k in keys_to_clean:
                try:
                    del store[k]
                except Exception:
                    pass
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


__all__ = ["WorkflowDAG", "WorkflowExecutionError", "WorkflowStage"]
