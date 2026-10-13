"""Perpetual security & concurrency audit - PHASE 11 (round-2) regression tests.

Round-2 re-audit of concurrency, io, dag, leases, upstream_protocol, and
redaction. Tests are written to FAIL ("red") against the current source (base
531641e, which already contains the phase 1-10 fixes) and must pass only after
the corresponding production fix lands. Production code is intentionally not
modified.

Findings covered here (NEW, not previously flagged):
1. ``redact_dict`` (redaction.py:155) does not mask ``set``/``frozenset``
   containers nested under a secret key. The ``_walk`` secret-context branch
   (:209-218) handles dict/list/tuple/str/bytes/bytearray/memoryview but not
   sets, so ``redact_dict({"token": {"tags": {"secret-a"}}})`` returns the set
   contents verbatim, leaking the secret values.
2. ``WorkflowDAG._topological_order`` (dag.py:154-195) is a recursive DFS with
   no depth bound. When stages are supplied children-before-parents (a valid,
   acyclic construction order), ``visit`` recurses the full dependency chain and
   raises ``RecursionError`` for a deep DAG that fits comfortably in memory
   (same class of defect fixed for provenance_graph in phase 7, but not here).
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.dag import WorkflowDAG, WorkflowStage
from gunz_utils.redaction import redact_dict

# -----------------------------------------------------------------------------
# redaction.py - set/frozenset under a secret key leaks unmasked
# -----------------------------------------------------------------------------


def test_redact_dict_masks_set_under_secret_key() -> None:
    """A ``set`` nested under a secret key must not leak its contents.

    ``redact_dict`` walks a secret-context value recursively (redaction.py:209),
    but the branch handles only dict/list/tuple and str/bytes/bytearray/
    memoryview. A ``set`` (or ``frozenset``) of strings falls through unchanged,
    so the secret values escape masking.
    """
    result = redact_dict({"token": {"tags": {"super-secret-token-1"}}})
    serialized = repr(result)
    assert "super-secret-token-1" not in serialized


def test_redact_dict_masks_frozenset_under_secret_key() -> None:
    """A ``frozenset`` under a secret key must also be masked."""
    result = redact_dict(
        {"credentials": {"scopes": frozenset({"access-cred-abc"})}}
    )
    serialized = repr(result)
    assert "access-cred-abc" not in serialized


# -----------------------------------------------------------------------------
# dag.py - _topological_order unbounded recursion on deep acyclic DAGs
# -----------------------------------------------------------------------------


def test_workflow_dag_topological_order_bounds_recursion() -> None:
    """``_topological_order`` must tolerate a deep acyclic DAG.

    ``WorkflowDAG.__init__`` calls ``_topological_order`` (dag.py:154), a
    recursive DFS with no depth bound. With stages added children-before-parents
    (a valid construction order), the top-level ``visit`` recurses the full
    chain and raises ``RecursionError`` even though the graph is acyclic and
    small enough to fit in memory.
    """
    stages: list[WorkflowStage] = []
    for index in range(1499, -1, -1):
        deps = (f"s{index - 1}",) if index else ()
        stages.append(
            WorkflowStage(name=f"s{index}", run=lambda ctx: 0, dependencies=deps)
        )

    dag = WorkflowDAG(stages)
    assert len(dag.order()) == 1500


# -----------------------------------------------------------------------------
# Sanity green - normal usage still works
# -----------------------------------------------------------------------------


def test_redact_dict_ordinary_dict_still_masked() -> None:
    """Sanity green: ordinary nested dicts/lists still mask secret leaves."""
    result = redact_dict({"nested": {"password": "hunter2", "name": "alice"}})
    assert "hunter2" not in result["nested"]["password"]
    assert "****" in result["nested"]["password"]
    assert result["nested"]["name"] == "alice"


def test_workflow_dag_small_dag_still_orders() -> None:
    """Sanity green: a small DAG still validates and orders correctly."""
    a = WorkflowStage(name="a", run=lambda ctx: 1, dependencies=())
    b = WorkflowStage(name="b", run=lambda ctx: 2, dependencies=("a",))
    dag = WorkflowDAG([b, a])
    assert list(dag.order()) == ["a", "b"]
