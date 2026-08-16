# dijkstra.py
# ============================================================
# Dijkstra's Single-Source Shortest-Path algorithm
# with full path reconstruction.
#
# Data structures used:
#   • heapq (Binary Min-Heap) – O(log V) push/pop
#   • dict  (HashMap)         – O(1) distance lookup
#   • dict  (predecessor map) – O(1) path reconstruction
#
# Complexity:
#   Time  : O((V + E) log V)  where V = vertices, E = edges
#   Space : O(V + E)
# ============================================================

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import heapq


def dijkstra(graph: dict, start: str) -> Tuple[Dict, Dict]:
    """
    Run Dijkstra's algorithm from `start` node and return
    both distance and predecessor maps.

    Parameters
    ----------
    graph : dict[str, dict[str, int]]
        Adjacency dictionary.  graph[u][v] = weight of edge u→v.
    start : str
        Source node key.

    Returns
    -------
    distances    : dict[str, float]
        Shortest distance from `start` to every reachable node.
        Unreachable nodes keep value float('inf').
    predecessors : dict[str, str | None]
        For each node, the node that precedes it on the
        shortest path from `start`.  predecessors[start] = None.

    Algorithm walk-through
    ----------------------
    1. Initialise all distances to ∞, except start = 0.
    2. Push (0, start) onto a min-heap priority queue.
    3. While the heap is non-empty:
         a. Pop the node with smallest tentative distance.
         b. Skip if already settled (stale entry).
         c. Relax all neighbours:
              new_dist = dist[u] + edge_weight(u, v)
              If new_dist < dist[v]:  update dist[v], record
              predecessor, push (new_dist, v) onto heap.
    4. Return distances and predecessor maps.

    Time Complexity  : O((V + E) log V)
      - Each vertex is extracted from the heap at most once: O(V log V)
      - Each edge is relaxed at most once, triggering a heap push:
        O(E log V)
    Space Complexity : O(V + E)
      - distances dict    : O(V)
      - predecessors dict : O(V)
      - heap              : O(V + E) in worst case
    """

    # ── Step 1: Initialise ────────────────────────────────────
    # Distance HashMap: all nodes start at infinity
    distances: Dict[str, float] = {node: float('inf') for node in graph}
    distances[start] = 0

    # Predecessor HashMap: tracks the shortest-path tree
    predecessors: Dict[str, Optional[str]] = {node: None for node in graph}

    # Min-Heap priority queue: (distance, node)
    # heapq in Python is a min-heap – smallest element always at index 0
    priority_queue: List[Tuple[float, str]] = [(0, start)]

    # ── Step 2-3: Main relaxation loop ────────────────────────
    while priority_queue:

        # Pop the node with the currently smallest distance – O(log V)
        current_distance, current_node = heapq.heappop(priority_queue)

        # Skip if this is a stale (outdated) entry in the heap
        # This handles duplicate entries pushed during relaxation
        if current_distance > distances[current_node]:
            continue

        # Relax all outgoing edges from current_node
        for neighbour, edge_weight in graph[current_node].items():

            # Tentative distance through current_node
            new_distance = current_distance + edge_weight

            # Relaxation step: update if shorter path found
            if new_distance < distances[neighbour]:
                distances[neighbour] = new_distance
                predecessors[neighbour] = current_node       # record path
                heapq.heappush(priority_queue,               # O(log V)
                               (new_distance, neighbour))

    return distances, predecessors


def reconstruct_path(predecessors: dict, start: str,
                     destination: str) -> List[str]:
    """
    Walk the predecessor map backwards to reconstruct the
    shortest path from `start` to `destination`.

    Parameters
    ----------
    predecessors : dict[str, str | None]
        Output of dijkstra().
    start        : source node
    destination  : target node

    Returns
    -------
    list[str] – ordered list of node names from start → destination.
    Returns [] if no path exists.

    Time Complexity  : O(V) – at most V steps to walk back
    Space Complexity : O(V) – path list
    """
    path = []
    current = destination

    # Walk backwards through the predecessor map
    while current is not None:
        path.append(current)
        current = predecessors.get(current)

        # Safety guard against cycles (shouldn't occur in a DAG-like usage)
        if current == destination:
            break

    path.reverse()  # reverse to get start → destination order

    # Validate that the path actually starts at `start`
    if path and path[0] == start:
        return path

    return []  # no valid path found