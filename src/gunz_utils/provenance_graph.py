"""Generic provenance graph for artifacts, datasets, jobs, and derived outputs."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
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

    def __init__(self,
        nodes: tuple[ProvenanceNode, ...] | list[ProvenanceNode] = (),
    ) -> None:
        self._nodes: dict[str, ProvenanceNode] = {}
        for node in nodes:
            self.add(node)

    @property
    def nodes(self) -> Mapping[str, ProvenanceNode]:
        """Return a read-only snapshot of known nodes.

        Returns
        -------
        Mapping[str, ProvenanceNode]
            The result of the operation.
        """
        from types import MappingProxyType

        return MappingProxyType(dict(self._nodes))

    def add(self,
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

    def get(self,
        identifier: str,
    ) -> ProvenanceNode:
        """Return a known node or raise KeyError.

        Parameters
        ----------
        identifier : str
            identifier parameter.

        Returns
        -------
        ProvenanceNode
            The result of the operation.
        """
        return self._nodes[identifier]

    def missing_inputs(self,
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

    def ancestors(self,
        identifier: str,
    ) -> tuple[str, ...]:
        """Return known transitive parent identifiers in stable traversal order.

        Parameters
        ----------
        identifier : str
            identifier parameter.

        Returns
        -------
        tuple[str, ...]
            The result of the operation.
        """
        if identifier not in self._nodes:
            raise KeyError(identifier)

        result: list[str] = []
        seen: set[str] = set()
        stack: list[Iterator[str]] = [iter(self._nodes[identifier].inputs)]

        while stack:
            try:
                parent = next(stack[-1])
            except StopIteration:
                stack.pop()
                continue

            if parent in seen or parent not in self._nodes:
                continue
            seen.add(parent)
            result.append(parent)
            stack.append(iter(self._nodes[parent].inputs))

        return tuple(result)

    def lineage(self,
        identifier: str,
    ) -> tuple[ProvenanceNode, ...]:
        """Return the target node followed by its known ancestors.

        Parameters
        ----------
        identifier : str
            identifier parameter.

        Returns
        -------
        tuple[ProvenanceNode, ...]
            The result of the operation.
        """
        return tuple(
            self._nodes[item]
            for item in (
                identifier,
                *self.ancestors(identifier),
            )
        )

    def _validate_acyclic(self) -> None:
        """Reject cycles among currently known nodes.

        No parameters and no return value.
        """
        visiting: set[str] = set()
        visited: set[str] = set()

        for start_identifier in self._nodes:
            if start_identifier in visited:
                continue

            visiting.add(start_identifier)
            stack: list[tuple[str, Iterator[str]]] = [
                (start_identifier, iter(self._nodes[start_identifier].inputs))
            ]

            while stack:
                identifier, it = stack[-1]
                try:
                    parent = next(it)
                except StopIteration:
                    stack.pop()
                    visiting.remove(identifier)
                    visited.add(identifier)
                    continue

                if parent not in self._nodes:
                    continue
                if parent in visited:
                    continue
                if parent in visiting:
                    raise ValueError("provenance graph cycle detected")

                visiting.add(parent)
                stack.append(
                    (parent, iter(self._nodes[parent].inputs))
                )


__all__ = ["ProvenanceGraph", "ProvenanceNode"]
