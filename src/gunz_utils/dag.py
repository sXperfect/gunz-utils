"""Dependency-ordered workflow DAG execution with fingerprint caching."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from .hashing import structured_hash


@dataclass(frozen=True)
class WorkflowStage:
    """One named stage in a dependency DAG.

    Parameters
    ----------
    name : str
        Unique stage name.
    run : Callable[[Mapping[str, Any]], Any]
        Stage function receiving completed direct-dependency outputs.
    dependencies : tuple[str, ...], optional
        Names of prerequisite stages.
    fingerprint : str | None, optional
        Caller-defined fingerprint for the stage's own configuration/input.
        A stage is cacheable only when it and every transitive dependency have
        fingerprints.
    """

    name: str
    run: Callable[[Mapping[str, Any]], Any]
    dependencies: tuple[str, ...] = ()
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        """Validate stage identity, callable and dependency declaration."""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("stage name must be a non-empty string")
        if not callable(self.run):
            raise TypeError("stage run must be callable")

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


class WorkflowDAG:
    """Execute named stages in topological order with safe cache propagation."""

    def __init__(
        self,
        stages: list[WorkflowStage] | tuple[WorkflowStage, ...],
    ) -> None:
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

        Notes
        -----
        Only stages with complete transitive fingerprint coverage are cached.
        This prevents a downstream stage from reusing stale output when an
        un-fingerprinted dependency may have changed.
        """
        store = cache if cache is not None else {}
        outputs: dict[str, Any] = {}

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
            output = stage.run(dependency_outputs)
            outputs[name] = output

            if key is not None:
                store[key] = output

        return outputs


__all__ = ["WorkflowDAG", "WorkflowStage"]
