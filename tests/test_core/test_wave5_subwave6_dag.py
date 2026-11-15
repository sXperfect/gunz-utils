"""Tests for Wave 5 Sub-Wave 6: Directed Acyclic Graphs (DAG) & Critical Path."""

import pytest

from gunz_utils.dag import (
    CycleError,
    add_edge,
    ancestors,
    critical_path,
    descendants,
    detect_cycles,
    has_path,
    is_dag,
    parallel_levels,
    subgraph,
    topological_sort,
    transitive_reduction,
)


def test_topological_sort_and_is_dag():
    # Linear graph: A -> B -> C
    graph = {"A": ["B"], "B": ["C"], "C": []}
    assert is_dag(graph)
    assert topological_sort(graph) == ["A", "B", "C"]
    assert detect_cycles(graph) == []

    # Cyclic graph: A -> B -> A
    cyclic = {"A": ["B"], "B": ["A"]}
    assert not is_dag(cyclic)
    assert len(detect_cycles(cyclic)) > 0
    with pytest.raises(CycleError):
        topological_sort(cyclic)


def test_parallel_levels():
    # A -> C, B -> C, C -> D
    graph = {"A": ["C"], "B": ["C"], "C": ["D"], "D": []}
    levels = parallel_levels(graph)
    assert len(levels) == 3
    assert levels[0] == {"A", "B"}
    assert levels[1] == {"C"}
    assert levels[2] == {"D"}


def test_ancestors_and_descendants():
    graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    assert descendants(graph, "A") == {"B", "C", "D"}
    assert descendants(graph, "D") == set()
    assert ancestors(graph, "D") == {"A", "B", "C"}
    assert ancestors(graph, "A") == set()


def test_has_path_and_subgraph():
    graph = {"A": ["B"], "B": ["C"], "C": ["D"], "E": []}
    assert has_path(graph, "A", "D")
    assert not has_path(graph, "A", "E")
    assert has_path(graph, "A", "A")

    sub = subgraph(graph, ["A", "B", "E"])
    assert sub == {"A": {"B"}, "B": set(), "E": set()}


def test_transitive_reduction():
    # Graph with shortcut: A -> B -> C and A -> C
    graph = {"A": ["B", "C"], "B": ["C"], "C": []}
    red = transitive_reduction(graph)
    assert red["A"] == {"B"}
    assert red["B"] == {"C"}
    assert red["C"] == set()


def test_critical_path():
    graph = {
        "A": ["B", "C"],
        "B": ["D"],
        "C": ["D"],
        "D": [],
    }
    weights = {
        "A": 2.0,
        "B": 5.0,
        "C": 1.0,
        "D": 3.0,
    }
    # Path A -> B -> D: 2 + 5 + 3 = 10
    # Path A -> C -> D: 2 + 1 + 3 = 6
    path, max_weight = critical_path(graph, weights)
    assert path == ["A", "B", "D"]
    assert max_weight == 10.0


def test_add_edge():
    g = {}
    add_edge(g, "X", "Y")
    add_edge(g, "Y", "Z")
    assert g["X"] == {"Y"}
    assert g["Y"] == {"Z"}
    assert g["Z"] == set()
