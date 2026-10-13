"""Additional deterministic testing helpers and property generators."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import random
import string
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_ALPHABET = string.ascii_letters + string.digits + " _-.:/@"


@dataclass
class ManualClock:
    """Deterministic monotonic clock for simulation and testing."""

    now: float = 0.0

    def monotonic(self) -> float:
        """monotonic() function.

        Returns
        -------
        float
            The result of the operation.
        """
        return self.now

    def advance(self,
        seconds: float,
    ) -> None:
        """advance() function.

        Parameters
        ----------
        seconds : float
            seconds parameter.
        """
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or seconds < 0
        ):
            raise ValueError(
                "clock advance must be a finite non-negative number"
            )
        try:
            seconds_float = float(seconds)
        except OverflowError:
            #? An int too large to convert to float must surface as the
            #? documented ValueError, not leak an internal OverflowError.
            raise ValueError(
                "clock advance must be a finite non-negative number"
            ) from None
        if not math.isfinite(seconds_float):
            raise ValueError(
                "clock advance must be a finite non-negative number"
            )
        candidate = self.now + seconds_float
        if not math.isfinite(candidate):
            raise OverflowError("manual clock exceeds finite float range")
        self.now = candidate


class PropertyFailure(AssertionError):
    """Raised when a property assertion fails on generated test inputs."""

    def __init__(self,
        message: str,
        *,
        iteration: int,
        sample: Any,
        seed: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.iteration = iteration
        self.sample = sample
        self.seed = seed
        self.cause = cause
        details = (
            f"{message} (iteration={iteration}, seed={seed}, sample={sample!r})"
        )
        super().__init__(details)


def fuzz_integers(
    *,
    seed: int,
    count: int,
    minimum: int = 0,
    maximum: int = 2**31 - 1,
) -> Iterator[int]:
    """Yield deterministic pseudo-random integers for lightweight fuzz tests.

    Parameters
    ----------
    seed : int
        seed parameter.
    count : int
        count parameter.
    minimum : int
        minimum parameter.
    maximum : int
        maximum parameter.

    Returns
    -------
    Iterator[int]
        The result of the operation.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    for name, value in (("minimum", minimum), ("maximum", maximum)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
    if minimum > maximum:
        raise ValueError("minimum must be <= maximum")
    rng = random.Random(seed)
    for _ in range(count):
        yield rng.randint(minimum, maximum)


def fuzz_floats(
    *,
    seed: int,
    count: int,
    minimum: float = -1e9,
    maximum: float = 1e9,
    allow_nan: bool = False,
    allow_infinity: bool = False,
) -> Iterator[float]:
    """Yield deterministic pseudo-random floats with optional special values.

    Parameters
    ----------
    seed : int
        seed parameter.
    count : int
        count parameter.
    minimum : float
        minimum parameter.
    maximum : float
        maximum parameter.
    allow_nan : bool
        allow_nan parameter.
    allow_infinity : bool
        allow_infinity parameter.

    Returns
    -------
    Iterator[float]
        The result of the operation.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    for name, value in (("minimum", minimum), ("maximum", maximum)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        try:
            converted = float(value)
        except OverflowError:
            #? An int too large to convert to float must surface as the
            #? documented ValueError, not leak an internal OverflowError.
            raise ValueError(f"{name} must be a finite number") from None
        if not math.isfinite(converted):
            raise ValueError(f"{name} must be a finite number")
    min_f = float(minimum)
    max_f = float(maximum)
    if min_f > max_f:
        raise ValueError("minimum must be <= maximum")

    rng = random.Random(seed)
    specials: list[float] = []
    if allow_nan:
        specials.append(float("nan"))
    if allow_infinity:
        specials.extend([float("inf"), float("-inf")])

    for _ in range(count):
        if specials and rng.random() < 0.1:
            yield rng.choice(specials)
        else:
            #? `random.uniform(a, b)` computes `a + (b - a) * random()`,
            #? whose `b - a` overflows to `inf` for a wide span, yielding
            #? special values even with allow_infinity=False. Interpolate
            #? instead so a finite range never produces inf/nan.
            r = rng.random()
            yield min_f * (1.0 - r) + max_f * r


def fuzz_strings(
    *,
    seed: int,
    count: int,
    min_length: int = 0,
    max_length: int = 64,
    alphabet: str | None = None,
) -> Iterator[str]:
    """Yield deterministic pseudo-random strings with a configurable alphabet.

    Parameters
    ----------
    seed : int
        seed parameter.
    count : int
        count parameter.
    min_length : int
        min_length parameter.
    max_length : int
        max_length parameter.
    alphabet : str | None
        alphabet parameter.

    Returns
    -------
    Iterator[str]
        The result of the operation.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    for name, value in (("min_length", min_length), ("max_length", max_length)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if min_length > max_length:
        raise ValueError("min_length must be <= max_length")

    chars = DEFAULT_ALPHABET if alphabet is None else alphabet
    if not chars and max_length > 0:
        raise ValueError("alphabet cannot be empty when max_length > 0")

    rng = random.Random(seed)
    for _ in range(count):
        length = rng.randint(min_length, max_length)
        if length == 0:
            yield ""
        else:
            yield "".join(rng.choices(chars, k=length))


def fuzz_bytes(
    *,
    seed: int,
    count: int,
    min_length: int = 0,
    max_length: int = 64,
) -> Iterator[bytes]:
    """Yield deterministic pseudo-random byte sequences.

    Parameters
    ----------
    seed : int
        seed parameter.
    count : int
        count parameter.
    min_length : int
        min_length parameter.
    max_length : int
        max_length parameter.

    Returns
    -------
    Iterator[bytes]
        The result of the operation.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    for name, value in (("min_length", min_length), ("max_length", max_length)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if min_length > max_length:
        raise ValueError("min_length must be <= max_length")

    rng = random.Random(seed)
    for _ in range(count):
        length = rng.randint(min_length, max_length)
        yield rng.randbytes(length)


def fuzz_primitives(
    *,
    seed: int,
    count: int,
) -> Iterator[int | float | str | bool | None]:
    """Yield deterministic scalar primitives (int, float, str, bool, None).

    Parameters
    ----------
    seed : int
        seed parameter.
    count : int
        count parameter.

    Returns
    -------
    Iterator[int | float | str | bool | None]
        The result of the operation.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")

    rng = random.Random(seed)
    for _ in range(count):
        choice = rng.randint(0, 4)
        if choice == 0:
            yield rng.randint(-10000, 10000)
        elif choice == 1:
            yield round(rng.uniform(-1000.0, 1000.0), 4)
        elif choice == 2:
            length = rng.randint(0, 16)
            yield "".join(rng.choices(DEFAULT_ALPHABET, k=length))
        elif choice == 3:
            yield bool(rng.randint(0, 1))
        else:
            yield None


def _generate_nested_json(
    rng: random.Random,
    *,
    current_depth: int,
    max_depth: int,
    max_breadth: int,
) -> Any:
    """_generate_nested_json() function.

    Parameters
    ----------
    rng : random.Random
        rng parameter.
    current_depth : int
        current_depth parameter.
    max_depth : int
        max_depth parameter.
    max_breadth : int
        max_breadth parameter.

    Returns
    -------
    Any
        The result of the operation.
    """
    if current_depth >= max_depth:
        choice = rng.randint(0, 4)
        if choice == 0:
            return rng.randint(-1000, 1000)
        if choice == 1:
            return round(rng.uniform(-100.0, 100.0), 3)
        if choice == 2:
            return "".join(rng.choices(string.ascii_letters, k=rng.randint(1, 8)))
        if choice == 3:
            return bool(rng.randint(0, 1))
        return None

    node_type = rng.randint(0, 2)
    if node_type == 0:
        #? dict
        size = rng.randint(0, max_breadth)
        result_dict: dict[str, Any] = {}
        for _ in range(size):
            key = "".join(rng.choices(string.ascii_lowercase, k=rng.randint(2, 6)))
            result_dict[key] = _generate_nested_json(
                rng,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                max_breadth=max_breadth,
            )
        return result_dict
    if node_type == 1:
        #? list
        size = rng.randint(0, max_breadth)
        return [
            _generate_nested_json(
                rng,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                max_breadth=max_breadth,
            )
            for _ in range(size)
        ]
    #? scalar
    return _generate_nested_json(
        rng,
        current_depth=max_depth,
        max_depth=max_depth,
        max_breadth=max_breadth,
    )


def fuzz_json_objects(
    *,
    seed: int,
    count: int,
    max_depth: int = 3,
    max_breadth: int = 4,
) -> Iterator[dict[str, Any] | list[Any]]:
    """Yield deterministic nested JSON structures (dicts and lists).

    Parameters
    ----------
    seed : int
        seed parameter.
    count : int
        count parameter.
    max_depth : int
        max_depth parameter.
    max_breadth : int
        max_breadth parameter.

    Returns
    -------
    Iterator[dict[str, Any] | list[Any]]
        The result of the operation.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if (
        isinstance(max_depth, bool)
        or not isinstance(max_depth, int)
        or max_depth < 1
    ):
        raise ValueError("max_depth must be an integer >= 1")
    if (
        isinstance(max_breadth, bool)
        or not isinstance(max_breadth, int)
        or max_breadth < 1
    ):
        raise ValueError("max_breadth must be an integer >= 1")

    rng = random.Random(seed)
    for _ in range(count):
        obj = _generate_nested_json(
            rng,
            current_depth=1,
            max_depth=max_depth,
            max_breadth=max_breadth,
        )
        if isinstance(obj, (dict, list)):
            yield obj
        else:
            yield {"value": obj}


def check_property(
    generator: Iterable[T],
    predicate: Callable[[T], None | bool],
    *,
    max_examples: int | None = None,
    seed: int | None = None,
) -> int:
    """Test a property predicate against samples from an iterable.

    Args:
        generator: Iterable supplying candidate inputs.
        predicate: Callable returning True/None on success, or False/raising on
            failure.
        max_examples: Maximum number of samples to evaluate before succeeding.
        seed: Optional reproduction seed to attach to error reports.

    Returns:
        The total number of examples verified.

    Raises:
        PropertyFailure: If the predicate returns False or raises an exception.
    """
    if (
        max_examples is not None
        and (
            isinstance(max_examples, bool)
            or not isinstance(max_examples, int)
            or max_examples < 0
        )
    ):
        raise ValueError("max_examples must be a non-negative integer")

    completed = 0
    for idx, sample in enumerate(generator):
        if max_examples is not None and completed >= max_examples:
            break
        try:
            result = predicate(sample)
            if result is False:
                raise PropertyFailure(
                    "property predicate returned False",
                    iteration=idx,
                    sample=sample,
                    seed=seed,
                )
        except PropertyFailure:
            raise
        except Exception as exc:
            raise PropertyFailure(
                f"property raised exception: {type(exc).__name__}: {exc}",
                iteration=idx,
                sample=sample,
                seed=seed,
                cause=exc,
            ) from exc
        completed += 1

    return completed


__all__ = [
    "ManualClock",
    "PropertyFailure",
    "check_property",
    "fuzz_bytes",
    "fuzz_floats",
    "fuzz_integers",
    "fuzz_json_objects",
    "fuzz_primitives",
    "fuzz_strings",
]
