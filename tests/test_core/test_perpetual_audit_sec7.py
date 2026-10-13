"""Perpetual security & concurrency audit - PHASE 7 regression tests.

Each test exposes a concrete correctness, resource-bound, or metadata-preservation
defect in the audited modules (concurrency, io, project, provenance_graph,
resilience). Tests are written to FAIL ("red") against the current source and
must pass only after the corresponding production fix lands. Production code is
intentionally not modified.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import stat
import tempfile

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.io import atomic_write
from gunz_utils.provenance_graph import ProvenanceGraph, ProvenanceNode

# -----------------------------------------------------------------------------
# provenance_graph.py - unbounded recursion in ancestors()
# -----------------------------------------------------------------------------


def test_provenance_graph_ancestors_bounds_recursion() -> None:
    """``ancestors`` must tolerate a deep acyclic lineage without ``RecursionError``.

    ``ProvenanceGraph.ancestors`` walks known parents with recursive ``walk``
    (provenance_graph.py:217-236) and no depth bound, so a valid deep DAG
    (>= ~1000 known ancestors, well under Python's recursion limit at build
    time because nodes are inserted topologically) raises ``RecursionError``
    instead of returning the lineage. ``lineage`` and ``missing_inputs`` with an
    identifier inherit the same defect.
    """
    graph = ProvenanceGraph()
    for index in range(1500):
        parent = (f"n{index - 1}",) if index else ()
        graph.add(ProvenanceNode(identifier=f"n{index}", kind="k", inputs=parent))

    ancestors = graph.ancestors("n1499")
    assert len(ancestors) == 1499


# -----------------------------------------------------------------------------
# provenance_graph.py - unbounded recursion in _validate_acyclic() on add
# -----------------------------------------------------------------------------


def test_provenance_graph_add_bounds_cycle_validation_recursion() -> None:
    """Adding nodes in non-topological order must not blow the Python stack.

    ``_validate_acyclic`` (provenance_graph.py:269-290) is a recursive DFS with
    no depth bound. When nodes are added children-before-parents (a valid,
    acyclic construction order), the top-level visit recurses the full chain
    and raises ``RecursionError`` from ``add`` even though the graph is acyclic
    and small enough to fit in memory.
    """
    graph = ProvenanceGraph()
    for index in range(1499, -1, -1):
        parent = (f"n{index - 1}",) if index else ()
        graph.add(ProvenanceNode(identifier=f"n{index}", kind="k", inputs=parent))

    assert len(graph.nodes) == 1500


# -----------------------------------------------------------------------------
# io.py - atomic_write silently resets an existing file's mode to 0600
# -----------------------------------------------------------------------------


def test_atomic_write_preserves_existing_file_permissions() -> None:
    """``atomic_write`` must not strip group/other access on an existing file.

    The temporary file is created via ``tempfile.mkstemp`` (mode 0600) and
    published with ``os.replace``, so when ``permissions`` is not provided the
    existing target's mode is silently replaced with 0600
    (io.py:82-111). Updating an existing 0644 (group/world-readable) file
    therefore removes its readability even though the caller never asked for a
    permission change. An atomic write should preserve an existing target's
    mode when ``permissions`` is not explicitly given.
    """
    directory = tempfile.mkdtemp()
    target = os.path.join(directory, "config")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("old")
    os.chmod(target, 0o644)

    atomic_write(target, "new")

    assert stat.S_IMODE(os.stat(target).st_mode) == 0o644


# -----------------------------------------------------------------------------
# provenance_graph.py - cycle detection still works (sanity green)
# -----------------------------------------------------------------------------


def test_provenance_graph_still_detects_cycle() -> None:
    """Sanity green: cycle detection remains correct on small graphs."""
    graph = ProvenanceGraph()
    graph.add(ProvenanceNode(identifier="a", kind="k", inputs=("b",)))
    graph.add(ProvenanceNode(identifier="b", kind="k", inputs=("c",)))
    with pytest.raises(ValueError, match="cycle"):
        graph.add(ProvenanceNode(identifier="c", kind="k", inputs=("a",)))
