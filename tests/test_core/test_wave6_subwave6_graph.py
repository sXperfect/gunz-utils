"""Tests for Wave 6 Sub-Wave 6: General Graph Algorithms."""

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.graph import (
    all_pairs_reachability,
    breadth_first_search,
    depth_first_search,
    dijkstra,
    find_connected_components,
    graph_diameter,
    is_bipartite,
    minimum_spanning_tree,
    strongly_connected_components,
)


def test_bfs_dfs():
    graph = {"A": ["B", "C"], "B": ["D"], "C": [], "D": []}
    bfs_res = breadth_first_search(graph, "A")
    assert bfs_res == ["A", "B", "C", "D"]

    dfs_res = depth_first_search(graph, "A")
    assert dfs_res == ["A", "B", "D", "C"]


def test_dijkstra():
    graph = {
        "A": {"B": 1.0, "C": 4.0},
        "B": {"C": 2.0, "D": 5.0},
        "C": {"D": 1.0},
        "D": {},
    }
    dists, paths = dijkstra(graph, "A")
    assert dists["A"] == 0.0
    assert dists["B"] == 1.0
    assert dists["C"] == 3.0  #? A -> B -> C: 1 + 2 = 3
    assert dists["D"] == 4.0  #? A -> B -> C -> D: 3 + 1 = 4
    assert paths["D"] == ["A", "B", "C", "D"]


def test_strongly_connected_components():
    graph = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A", "D"],
        "D": ["E"],
        "E": ["D"],
    }
    sccs = strongly_connected_components(graph)
    #? {A, B, C} and {D, E}
    assert {"A", "B", "C"} in sccs
    assert {"D", "E"} in sccs


def test_bipartite_and_connected_components():
    #? Bipartite square: 1-2, 2-3, 3-4, 4-1
    square = {"1": ["2", "4"], "2": ["1", "3"], "3": ["2", "4"], "4": ["1", "3"]}
    assert is_bipartite(square)

    #? Triangle (odd cycle) is not bipartite
    triangle = {"1": ["2", "3"], "2": ["1", "3"], "3": ["1", "2"]}
    assert not is_bipartite(triangle)

    comps = find_connected_components({"1": ["2"], "2": [], "3": []})
    assert len(comps) == 2


def test_minimum_spanning_tree():
    edges = [
        ("A", "B", 1.0),
        ("B", "C", 2.0),
        ("A", "C", 3.0),
    ]
    mst = minimum_spanning_tree(edges)
    assert len(mst) == 2
    assert sum(w for _, _, w in mst) == 3.0


def test_graph_diameter_and_reachability():
    graph = {
        "A": {"B": 2.0},
        "B": {"C": 3.0},
        "C": {},
    }
    assert graph_diameter(graph) == 5.0

    unweighted = {"A": ["B"], "B": ["C"], "C": []}
    reach = all_pairs_reachability(unweighted)
    assert reach["A"] == {"A", "B", "C"}
    assert reach["B"] == {"B", "C"}
    assert reach["C"] == {"C"}
