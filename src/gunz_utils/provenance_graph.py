"""Generic provenance graph for artifacts, datasets, jobs, and derived outputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .structures import freeze_structure


@dataclass(frozen=True, slots=True)
class ProvenanceNode:
    """Immutable node in a provenance graph.

    Parameters
    ----------
    identifier : str
        Unique stable identifier, such as a digest, run ID, or object key.
    kind : str
        Caller-defined node category.
    producer : str | None, optional
        Optional producer/tool/stage identifier.
    inputs : tuple[str, ...], optional
        Direct parent identifiers.
    metadata : Mapping[str, Any], optional
        Caller metadata defensively copied into an immutable mapping.
    """

    identifier: str
    kind: str
    producer: str | None = None
    inputs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate identity/dependencies and freeze metadata."""
        if not isinstance(self.identifier, str) or not self.identifier:
            raise ValueError("identifier must be a non-empty string")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("kind must be a non-empty string")
        if self.producer is not None and (
            not isinstance(self.producer, str)
            or not self.producer
        ):
            raise ValueError("producer must be None or a non-empty string")
        if any(
            not isinstance(item, str) or not item
            for item in self.inputs
        ):
            raise ValueError("inputs must contain non-empty string identifiers")
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError("inputs must not contain duplicates")
        if self.identifier in self.inputs:
            raise ValueError("node cannot directly depend on itself")

        object.__setattr__(
            self,
            "inputs",
            tuple(self.inputs),
        )
        object.__setattr__(
            self,
            "metadata",
            freeze_structure(dict(self.metadata)),
        )


class ProvenanceGraph:
    """Directed acyclic provenance graph with optional unresolved inputs.

    Unknown input identifiers are allowed so graphs can reference external
    artifacts that are not materialized locally. When those inputs are added
    later, cycle validation is performed against the complete known graph.
    """

    def __init__(
        self,
        nodes: tuple[ProvenanceNode, ...] | list[ProvenanceNode] = (),
    ) -> None:
        self._nodes: dict[str, ProvenanceNode] = {}
        for node in nodes:
            self.add(node)

    @property
    def nodes(self) -> Mapping[str, ProvenanceNode]:
        """Return a read-only snapshot of known nodes."""
        from types import MappingProxyType

        return MappingProxyType(dict(self._nodes))

    def add(
        self,
        node: ProvenanceNode,
        *,
        replace: bool = False,
    ) -> ProvenanceNode:
        """Add a node and reject conflicting identifiers or cycles.

        Parameters
        ----------
        node : ProvenanceNode
            Node to insert.
        replace : bool, optional
            Permit replacing an existing node with the same identifier.

        Returns
        -------
        ProvenanceNode
            Inserted node.

        Raises
        ------
        ValueError
            If the identifier already exists without replace, or the resulting
            known graph contains a cycle.
        """
        existing = self._nodes.get(node.identifier)
        if existing is not None and not replace:
            if existing == node:
                return existing
            raise ValueError(
                f"provenance node already exists: {node.identifier!r}"
            )

        previous = existing
        self._nodes[node.identifier] = node
        try:
            self._validate_acyclic()
        except Exception:
            if previous is None:
                self._nodes.pop(node.identifier, None)
            else:
                self._nodes[node.identifier] = previous
            raise
        return node

    def get(
        self,
        identifier: str,
    ) -> ProvenanceNode:
        """Return a known node or raise KeyError."""
        return self._nodes[identifier]

    def missing_inputs(
        self,
        identifier: str | None = None,
    ) -> tuple[str, ...]:
        """Return unresolved parent identifiers.

        Parameters
        ----------
        identifier : str | None, optional
            Restrict the search to one node and its known ancestors. When None,
            inspect the whole graph.
        """
        if identifier is None:
            nodes = tuple(self._nodes.values())
        else:
            nodes = tuple(
                self._nodes[item]
                for item in (
                    identifier,
                    *self.ancestors(identifier),
                )
            )

        missing = {
            parent
            for node in nodes
            for parent in node.inputs
            if parent not in self._nodes
        }
        return tuple(sorted(missing))

    def ancestors(
        self,
        identifier: str,
    ) -> tuple[str, ...]:
        """Return known transitive parent identifiers in stable traversal order."""
        if identifier not in self._nodes:
            raise KeyError(identifier)

        result: list[str] = []
        seen: set[str] = set()

        def walk(current: str) -> None:
            node = self._nodes[current]
            for parent in node.inputs:
                if parent in seen or parent not in self._nodes:
                    continue
                seen.add(parent)
                result.append(parent)
                walk(parent)

        walk(identifier)
        return tuple(result)

    def lineage(
        self,
        identifier: str,
    ) -> tuple[ProvenanceNode, ...]:
        """Return the target node followed by its known ancestors."""
        return tuple(
            self._nodes[item]
            for item in (
                identifier,
                *self.ancestors(identifier),
            )
        )

    def _validate_acyclic(self) -> None:
        """Reject cycles among currently known nodes."""
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(identifier: str) -> None:
            if identifier in visited:
                return
            if identifier in visiting:
                raise ValueError("provenance graph cycle detected")

            visiting.add(identifier)
            node = self._nodes[identifier]
            for parent in node.inputs:
                if parent in self._nodes:
                    visit(parent)
            visiting.remove(identifier)
            visited.add(identifier)

        for identifier in self._nodes:
            visit(identifier)


__all__ = ["ProvenanceGraph", "ProvenanceNode"]
