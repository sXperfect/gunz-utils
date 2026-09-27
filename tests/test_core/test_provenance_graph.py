"""Tests for generic provenance graphs."""

from __future__ import annotations

import pytest

from gunz_utils.provenance_graph import ProvenanceGraph, ProvenanceNode


def test_provenance_graph_tracks_known_ancestors_and_external_inputs() -> None:
    graph = ProvenanceGraph(
        [
            ProvenanceNode(
                "raw",
                "dataset",
                inputs=("external-source",),
            ),
            ProvenanceNode(
                "features",
                "artifact",
                inputs=("raw",),
            ),
            ProvenanceNode(
                "model",
                "artifact",
                inputs=("features",),
            ),
        ]
    )

    assert graph.ancestors("model") == (
        "features",
        "raw",
    )
    assert graph.missing_inputs("model") == ("external-source",)
    assert [node.identifier for node in graph.lineage("model")] == [
        "model",
        "features",
        "raw",
    ]


def test_provenance_node_defensively_freezes_metadata() -> None:
    metadata = {
        "nested": {
            "value": 1,
        }
    }
    node = ProvenanceNode(
        "artifact",
        "file",
        metadata=metadata,
    )

    metadata["nested"]["value"] = 2

    assert node.metadata["nested"]["value"] == 1
    with pytest.raises(TypeError):
        node.metadata["other"] = 1

    nested = node.metadata["nested"]
    assert isinstance(nested, dict) is False
    with pytest.raises(TypeError):
        nested["value"] = 3


def test_provenance_graph_rejects_conflicting_duplicate_identifier() -> None:
    graph = ProvenanceGraph(
        [ProvenanceNode("same", "first")]
    )

    assert graph.add(
        ProvenanceNode("same", "first")
    ).kind == "first"

    with pytest.raises(ValueError, match="already exists"):
        graph.add(
            ProvenanceNode("same", "second")
        )


def test_provenance_graph_detects_cycle_added_out_of_order() -> None:
    graph = ProvenanceGraph()
    graph.add(
        ProvenanceNode(
            "a",
            "artifact",
            inputs=("b",),
        )
    )

    with pytest.raises(ValueError, match="cycle"):
        graph.add(
            ProvenanceNode(
                "b",
                "artifact",
                inputs=("a",),
            )
        )

    assert "b" not in graph.nodes
    assert graph.missing_inputs("a") == ("b",)


def test_provenance_graph_replace_rolls_back_on_cycle() -> None:
    graph = ProvenanceGraph(
        [
            ProvenanceNode("a", "artifact"),
            ProvenanceNode(
                "b",
                "artifact",
                inputs=("a",),
            ),
        ]
    )

    with pytest.raises(ValueError, match="cycle"):
        graph.add(
            ProvenanceNode(
                "a",
                "artifact",
                inputs=("b",),
            ),
            replace=True,
        )

    assert graph.get("a").inputs == ()


def test_provenance_node_rejects_cyclic_metadata() -> None:
    metadata: dict[str, object] = {}
    metadata["self"] = metadata

    with pytest.raises(ValueError, match="cycle"):
        ProvenanceNode(
            "cyclic",
            "artifact",
            metadata=metadata,
        )
