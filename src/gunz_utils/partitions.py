"""Stable manifests for disjoint named partitions."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .hashing import structured_hash
from .io import atomic_write
from .serialization import json_dumps


@dataclass(frozen=True)
class PartitionManifest:
    """Immutable named partitions with overlap and duplicate validation.

    Parameters
    ----------
    partitions : Mapping[str, Iterable[str]]
        Partition names mapped to stable item identifiers.
    """

    partitions: Mapping[str, Iterable[str]]

    def __post_init__(self) -> None:
        """Normalize caller input into an immutable mapping of tuples."""
        normalized: dict[str, tuple[str, ...]] = {}
        for name, identifiers in self.partitions.items():
            if isinstance(identifiers, (str, bytes, bytearray)):
                raise ValueError(
                    f"partition {name!r} identifiers must be an iterable "
                    "of strings, not one string"
                )
            normalized[name] = tuple(identifiers)
        object.__setattr__(
            self,
            "partitions",
            MappingProxyType(normalized),
        )
        self.validate()

    def validate(self) -> None:
        """Validate names, duplicates within partitions, and cross-partition overlap."""
        if not self.partitions:
            raise ValueError("partitions must not be empty")

        seen: dict[str, str] = {}
        for name, identifiers in self.partitions.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("partition names must be non-empty strings")
            identifiers_tuple = tuple(identifiers)
            if len(set(identifiers_tuple)) != len(identifiers_tuple):
                raise ValueError(
                    f"duplicate item identifiers in partition {name!r}"
                )
            for identifier in identifiers_tuple:
                if not isinstance(identifier, str) or not identifier:
                    raise ValueError(
                        f"partition {name!r} contains an invalid item identifier"
                    )
                previous = seen.get(identifier)
                if previous is not None:
                    raise ValueError(
                        f"item {identifier!r} appears in partitions "
                        f"{previous!r} and {name!r}"
                    )
                seen[identifier] = name

    @property
    def fingerprint(self) -> str:
        """Return a deterministic fingerprint of partition assignments."""
        self.validate()
        normalized = {
            name: list(identifiers)
            for name, identifiers in sorted(self.partitions.items())
        }
        return structured_hash(normalized)

    def write(
        self,
        path: str | Path,
        *,
        durable: bool = False,
    ) -> Path:
        """Atomically persist partitions and their fingerprint as JSON."""
        self.validate()
        target = Path(path)
        payload = {
            "partitions": {
                name: list(identifiers)
                for name, identifiers in sorted(self.partitions.items())
            },
            "fingerprint": self.fingerprint,
        }
        atomic_write(
            target,
            json_dumps(payload, pretty=True) + "\n",
            mkdir=True,
            durable=durable,
        )
        return target


__all__ = [
    "PartitionManifest",
    "assert_disjoint_partitions",
    "partition_overlaps",
]



def partition_overlaps(
    partitions: Mapping[str, Iterable[Hashable]],
) -> dict[tuple[str, str], frozenset[Hashable]]:
    """Return non-empty pairwise overlaps between named partitions.

    Parameters
    ----------
    partitions : Mapping[str, Iterable[Hashable]]
        Named groups of hashable identifiers.

    Returns
    -------
    dict[tuple[str, str], frozenset[Hashable]]
        Pair names mapped to their shared identifiers. Empty intersections are
        omitted and pair ordering is deterministic by partition name.
    """
    groups: dict[str, set[Hashable]] = {}
    for name, values in partitions.items():
        if not isinstance(name, str) or not name:
            raise ValueError(
                "partition names must be non-empty strings"
            )
        groups[name] = set(values)

    names = sorted(groups)
    result: dict[
        tuple[str, str],
        frozenset[Hashable],
    ] = {}
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = groups[left] & groups[right]
            if overlap:
                result[(left, right)] = frozenset(overlap)
    return result


def assert_disjoint_partitions(
    partitions: Mapping[str, Iterable[Hashable]],
) -> None:
    """Require named partitions to have no shared identifiers."""
    overlaps = partition_overlaps(partitions)
    if overlaps:
        pairs = ", ".join(
            f"{left}/{right}"
            for left, right in overlaps
        )
        raise ValueError(
            f"partition overlap detected: {pairs}"
        )
