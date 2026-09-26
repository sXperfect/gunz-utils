"""Experiment matrices and repeated benchmark orchestration."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Callable

from .result import BenchmarkResult
from .runner import benchmark


@dataclass(frozen=True)
class ExperimentResult:
    parameters: dict[str, Any]
    repetition: int
    result: BenchmarkResult


def run_experiment(
    func: Callable[..., Any],
    *,
    parameters: dict[str, list[Any]],
    repetitions: int = 1,
    warmup: int = 3,
    iterations: int = 20,
    name: str | None = None,
) -> list[ExperimentResult]:
    """Run a Cartesian parameter matrix with explicit repetitions."""
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    keys = list(parameters)
    values = [parameters[key] for key in keys]
    if any(not value for value in values):
        raise ValueError("parameter value lists must not be empty")
    output: list[ExperimentResult] = []
    for combination in itertools.product(*values):
        kwargs = dict(zip(keys, combination))
        for repetition in range(repetitions):
            result = benchmark(
                func,
                name=name,
                warmup=warmup,
                iterations=iterations,
                parameters={**kwargs, "_repetition": repetition},
                **kwargs,
            )
            output.append(ExperimentResult(kwargs, repetition, result))
    return output


__all__ = ["ExperimentResult", "run_experiment"]
