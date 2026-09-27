"""Benchmark suites for reusable cross-project performance checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .result import BenchmarkResult
from .runner import benchmark


@dataclass
class BenchmarkCase:
    name: str
    func: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)


class BenchmarkSuite:
    """Collection of benchmark cases sharing runner configuration."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._cases: list[BenchmarkCase] = []

    def add(
        self,
        name: str,
        func: Callable[..., Any],
        *args: Any,
        parameters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> BenchmarkSuite:
        self._cases.append(
            BenchmarkCase(
                name=name,
                func=func,
                args=args,
                kwargs=kwargs,
                parameters={} if parameters is None else dict(parameters),
            )
        )
        return self

    def add_parameters(
        self,
        name: str,
        func: Callable[..., Any],
        parameter: str,
        values: list[Any],
        *args: Any,
        **kwargs: Any,
    ) -> BenchmarkSuite:
        """Add one case per value in a parameter sweep."""
        for value in values:
            case_kwargs = dict(kwargs)
            case_kwargs[parameter] = value
            self.add(
                f"{name}[{parameter}={value}]",
                func,
                *args,
                parameters={parameter: value},
                **case_kwargs,
            )
        return self

    def run(self, *, warmup: int = 3, iterations: int = 20) -> list[BenchmarkResult]:
        """Run every case in insertion order."""
        return [
            benchmark(
                case.func,
                *case.args,
                name=f"{self.name}.{case.name}",
                warmup=warmup,
                iterations=iterations,
                parameters=case.parameters,
                **case.kwargs,
            )
            for case in self._cases
        ]


__all__ = ["BenchmarkCase", "BenchmarkSuite"]
