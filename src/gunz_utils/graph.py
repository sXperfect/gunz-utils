"""General graph algorithms: Dijkstra, Tarjan's SCC, Kruskal's MST, and graph analysis."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")


def breadth_first_search(
    graph: Mapping[T, Iterable[T]],
    start: T,
) -> list[T]:
    """Traverse graph in breadth-first order starting from start node."""
    visited: set[T] = {start}
    order: list[T] = []
    queue: deque[T] = deque([start])

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph.get(node, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return order


def depth_first_search(
    graph: Mapping[T, Iterable[T]],
    start: T,
) -> list[T]:
    """Traverse graph in depth-first order starting from start node."""
    visited: set[T] = set()
    order: list[T] = []

    def dfs(
        node: T,
    ) -> None:
        visited.add(node)
        order.append(node)
        for neighbor in graph.get(node, ()):
            if neighbor not in visited:
                dfs(neighbor)

    dfs(start)
    return order


def dijkstra(
    graph: Mapping[T, Mapping[T, float]],
    start: T,
    end: T | None = None,
) -> tuple[dict[T, float], dict[T, list[T]]]:
    """Compute shortest path distances and paths using Dijkstra's algorithm.

    Returns
    -------
    tuple[dict[T, float], dict[T, list[T]]]
        (distances, paths) from start to all reachable nodes (or up to end).
    """
    distances: dict[T, float] = {start: 0.0}
    predecessors: dict[T, T | None] = {start: None}
    pq: list[tuple[float, int, T]] = [(0.0, 0, start)]
    entry_count = 0

    while pq:
        curr_dist, _, u = heapq.heappop(pq)
        if curr_dist > distances.get(u, float("inf")):
            continue
        if end is not None and u == end:
            break

        for v, weight in graph.get(u, {}).items():
            if weight < 0:
                raise ValueError("dijkstra cannot handle negative edge weights")
            new_dist = curr_dist + weight
            if new_dist < distances.get(v, float("inf")):
                distances[v] = new_dist
                predecessors[v] = u
                entry_count += 1
                heapq.heappush(pq, (new_dist, entry_count, v))

    paths: dict[T, list[T]] = {}
    for node in distances:
        path: list[T] = []
        curr: T | None = node
        while curr is not None:
            path.append(curr)
            curr = predecessors.get(curr)
        path.reverse()
        paths[node] = path

    return distances, paths


def strongly_connected_components(
    graph: Mapping[T, Iterable[T]],
) -> list[set[T]]:
    """Compute strongly connected components in a directed graph using Tarjan's algorithm."""
    index = 0
    indices: dict[T, int] = {}
    lowlinks: dict[T, int] = {}
    stack: list[T] = []
    on_stack: set[T] = set()
    sccs: list[set[T]] = []

    #? Ensure all nodes exist in adjacency list
    adj: dict[T, list[T]] = {k: list(v) for k, v in graph.items()}
    for neighbors in list(adj.values()):
        for n in neighbors:
            if n not in adj:
                adj[n] = []

    def strongconnect(
        v: T,
    ) -> None:
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj.get(v, ()):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: set[T] = set()
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.add(w)
                if w == v:
                    break
            sccs.append(scc)

    for node in adj:
        if node not in indices:
            strongconnect(node)

    return sccs


def is_bipartite(
    graph: Mapping[T, Iterable[T]],
) -> bool:
    """Return True if graph is bipartite (can be colored with two colors)."""
    color: dict[T, int] = {}

    for start_node in graph:
        if start_node in color:
            continue
        color[start_node] = 0
        queue = deque([start_node])
        while queue:
            u = queue.popleft()
            curr_c = color[u]
            next_c = 1 - curr_c
            for v in graph.get(u, ()):
                if v not in color:
                    color[v] = next_c
                    queue.append(v)
                elif color[v] == curr_c:
                    return False
    return True


def find_connected_components(
    graph: Mapping[T, Iterable[T]],
) -> list[set[T]]:
    """Find connected components in an undirected graph."""
    #? Undirected adjacency
    undirected: dict[T, set[T]] = {k: set(v) for k, v in graph.items()}
    for u, neighbors in list(undirected.items()):
        for v in neighbors:
            if v not in undirected:
                undirected[v] = set()
            undirected[v].add(u)

    visited: set[T] = set()
    components: list[set[T]] = []

    for node in undirected:
        if node not in visited:
            comp = set(breadth_first_search(undirected, node))
            visited.update(comp)
            components.append(comp)
    return components


def all_pairs_reachability(
    graph: Mapping[T, Iterable[T]],
) -> dict[T, set[T]]:
    """Compute transitive closure reachable nodes for all vertices."""
    adj = {k: list(v) for k, v in graph.items()}
    return {u: set(breadth_first_search(adj, u)) for u in adj}


def minimum_spanning_tree(
    edges: Sequence[tuple[T, T, float]],
) -> list[tuple[T, T, float]]:
    """Compute Minimum Spanning Tree of undirected edges using Kruskal's algorithm."""
    parent: dict[T, T] = {}
    rank: dict[T, int] = {}

    def find(
        i: T,
    ) -> T:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(
        i: T,
        j: T,
    ) -> bool:
        root_i = find(i)
        root_j = find(j)
        if root_i == root_j:
            return False
        if rank[root_i] < rank[root_j]:
            parent[root_i] = root_j
        elif rank[root_i] > rank[root_j]:
            parent[root_j] = root_i
        else:
            parent[root_j] = root_i
            rank[root_i] += 1
        return True

    sorted_edges = sorted(edges, key=lambda e: e[2])
    mst: list[tuple[T, T, float]] = []

    for u, v, _ in sorted_edges:
        if u not in parent:
            parent[u] = u
            rank[u] = 0
        if v not in parent:
            parent[v] = v
            rank[v] = 0

    for u, v, weight in sorted_edges:
        if union(u, v):
            mst.append((u, v, weight))

    return mst


def graph_diameter(
    graph: Mapping[T, Mapping[T, float]],
) -> float:
    """Compute the diameter (longest shortest-path distance) of a weighted graph."""
    max_dist = 0.0
    for start in graph:
        dists, _ = dijkstra(graph, start)
        for d in dists.values():
            if d > max_dist:
                max_dist = d
    return max_dist


def has_cycle_undirected(
    graph: Mapping[T, Iterable[T]],
) -> bool:
    """Return True if undirected graph contains any cycles."""
    visited: set[T] = set()

    for start in graph:
        if start in visited:
            continue
        queue = deque([(start, None)])
        visited.add(start)
        while queue:
            u, parent = queue.popleft()
            for v in graph.get(u, ()):
                if v not in visited:
                    visited.add(v)
                    queue.append((v, u))
                elif v != parent:
                    return True
    return False


def eulerian_path(
    graph: Mapping[T, Sequence[T]],
) -> list[T] | None:
    """Find an Eulerian path visiting every edge exactly once (Hierholzer's algorithm)."""
    adj: dict[T, list[T]] = {k: list(v) for k, v in graph.items()}
    in_deg: dict[T, int] = {k: 0 for k in adj}
    out_deg: dict[T, int] = {k: len(v) for k, v in adj.items()}

    for neighbors in adj.values():
        for v in neighbors:
            in_deg[v] = in_deg.get(v, 0) + 1
            if v not in adj:
                adj[v] = []
                out_deg[v] = 0

    start_nodes = [n for n in adj if out_deg[n] - in_deg.get(n, 0) == 1]
    end_nodes = [n for n in adj if in_deg.get(n, 0) - out_deg[n] == 1]

    if len(start_nodes) > 1 or len(end_nodes) > 1:
        return None

    curr = start_nodes[0] if start_nodes else next(iter(adj), None)
    if curr is None:
        return []

    path: list[T] = []
    stack: list[T] = [curr]

    while stack:
        u = stack[-1]
        if adj.get(u):
            nxt = adj[u].pop()
            stack.append(nxt)
        else:
            path.append(stack.pop())

    path.reverse()
    total_edges = sum(len(v) for v in graph.values())
    if len(path) != total_edges + 1:
        return None
    return path


__all__ = [
    "all_pairs_reachability",
    "breadth_first_search",
    "depth_first_search",
    "dijkstra",
    "eulerian_path",
    "find_connected_components",
    "graph_diameter",
    "has_cycle_undirected",
    "is_bipartite",
    "minimum_spanning_tree",
    "strongly_connected_components",
]
