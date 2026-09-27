"""Tests for dependency-ordered fingerprint-aware workflows."""

from __future__ import annotations

import pytest

from gunz_utils.dag import WorkflowDAG, WorkflowStage


def test_workflow_dag_executes_dependencies_before_consumers() -> None:
    calls: list[str] = []
    dag = WorkflowDAG(
        [
            WorkflowStage(
                "final",
                lambda deps: (
                    calls.append("final"),
                    deps["left"] + deps["right"],
                )[1],
                dependencies=("left", "right"),
                fingerprint="final-v1",
            ),
            WorkflowStage(
                "left",
                lambda _deps: (
                    calls.append("left"),
                    2,
                )[1],
                fingerprint="left-v1",
            ),
            WorkflowStage(
                "right",
                lambda _deps: (
                    calls.append("right"),
                    3,
                )[1],
                fingerprint="right-v1",
            ),
        ]
    )

    outputs = dag.execute()

    assert outputs["final"] == 5
    assert calls[-1] == "final"
    assert set(calls[:2]) == {"left", "right"}


def test_workflow_dag_rejects_missing_dependency_and_cycle() -> None:
    with pytest.raises(KeyError, match="missing stage dependency"):
        WorkflowDAG(
            [
                WorkflowStage(
                    "a",
                    lambda _deps: 1,
                    dependencies=("missing",),
                )
            ]
        )

    with pytest.raises(ValueError, match="cycle"):
        WorkflowDAG(
            [
                WorkflowStage(
                    "a",
                    lambda _deps: 1,
                    dependencies=("b",),
                ),
                WorkflowStage(
                    "b",
                    lambda _deps: 2,
                    dependencies=("a",),
                ),
            ]
        )


def test_workflow_cache_reuses_fingerprinted_stage() -> None:
    calls = {"source": 0}
    cache: dict[tuple[str, str], object] = {}

    def source(_deps: object) -> int:
        calls["source"] += 1
        return 7

    dag = WorkflowDAG(
        [
            WorkflowStage(
                "source",
                source,
                fingerprint="source-v1",
            )
        ]
    )

    assert dag.execute(cache=cache)["source"] == 7
    assert dag.execute(cache=cache)["source"] == 7
    assert calls["source"] == 1


def test_dependency_fingerprint_change_invalidates_downstream_cache() -> None:
    cache: dict[tuple[str, str], object] = {}
    calls = {"final": 0}

    def make_dag(source_fingerprint: str) -> WorkflowDAG:
        def final(deps: object) -> int:
            calls["final"] += 1
            assert isinstance(deps, dict)
            return int(deps["source"]) + 1

        return WorkflowDAG(
            [
                WorkflowStage(
                    "source",
                    lambda _deps: 1,
                    fingerprint=source_fingerprint,
                ),
                WorkflowStage(
                    "final",
                    final,
                    dependencies=("source",),
                    fingerprint="final-v1",
                ),
            ]
        )

    make_dag("source-v1").execute(cache=cache)
    make_dag("source-v1").execute(cache=cache)
    assert calls["final"] == 1

    make_dag("source-v2").execute(cache=cache)
    assert calls["final"] == 2


def test_unfingerprinted_dependency_disables_downstream_cache() -> None:
    calls = {"source": 0, "final": 0}
    cache: dict[tuple[str, str], object] = {}

    def source(_deps: object) -> int:
        calls["source"] += 1
        return calls["source"]

    def final(deps: object) -> int:
        calls["final"] += 1
        assert isinstance(deps, dict)
        return int(deps["source"])

    dag = WorkflowDAG(
        [
            WorkflowStage(
                "source",
                source,
                fingerprint=None,
            ),
            WorkflowStage(
                "final",
                final,
                dependencies=("source",),
                fingerprint="final-v1",
            ),
        ]
    )

    assert dag.execute(cache=cache)["final"] == 1
    assert dag.execute(cache=cache)["final"] == 2
    assert calls == {"source": 2, "final": 2}



def test_dependency_order_changes_effective_fingerprint() -> None:
    left = WorkflowDAG(
        [
            WorkflowStage(
                "a",
                lambda _deps: 1,
                fingerprint="a-v1",
            ),
            WorkflowStage(
                "b",
                lambda _deps: 2,
                fingerprint="b-v1",
            ),
            WorkflowStage(
                "final",
                lambda deps: tuple(deps),
                dependencies=("a", "b"),
                fingerprint="final-v1",
            ),
        ]
    )
    right = WorkflowDAG(
        [
            WorkflowStage(
                "a",
                lambda _deps: 1,
                fingerprint="a-v1",
            ),
            WorkflowStage(
                "b",
                lambda _deps: 2,
                fingerprint="b-v1",
            ),
            WorkflowStage(
                "final",
                lambda deps: tuple(deps),
                dependencies=("b", "a"),
                fingerprint="final-v1",
            ),
        ]
    )

    assert (
        left.effective_fingerprint("final")
        != right.effective_fingerprint("final")
    )


def test_workflow_stage_rejects_ambiguous_declarations() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        WorkflowStage(
            "stage",
            lambda _deps: None,
            dependencies=("a", "a"),
        )

    with pytest.raises(ValueError, match="itself"):
        WorkflowStage(
            "stage",
            lambda _deps: None,
            dependencies=("stage",),
        )

    with pytest.raises(ValueError, match="fingerprint"):
        WorkflowStage(
            "stage",
            lambda _deps: None,
            fingerprint="",
        )

    with pytest.raises(TypeError, match="callable"):
        WorkflowStage(
            "stage",
            object(),
        )
