"""Directed road graph and constrained Espacio-sequence routing."""

import heapq
import itertools
import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RoadEdge:
    edge_id: str
    from_node: str
    to_node: str
    length_m: float
    highway: str
    maxspeed: str | None = None
    espacio_id: int | None = None


@dataclass(frozen=True)
class PathResult:
    status: str  # VALID, INVALID, or INDETERMINATE
    reason: str | None
    edge_ids: tuple[str, ...]
    distance_m: float | None
    estimated_time_s: float | None


class GraphLike(Protocol):
    def get_edge(self, edge_id: str) -> RoadEdge | None: ...
    def iter_outgoing(self, node: str) -> list[RoadEdge]: ...
    def is_forbidden(self, incoming_id: str, outgoing_id: str) -> bool: ...
    def is_turn_uncertain(self, incoming_id: str, outgoing_id: str) -> bool: ...
    def travel_time_s(self, edge: RoadEdge) -> float: ...


class RoadGraph:
    def __init__(self, speed_defaults_kmh: dict[str, float]):
        self.speed_defaults_kmh = speed_defaults_kmh
        self.edges: dict[str, RoadEdge] = {}
        self.outgoing: dict[str, list[RoadEdge]] = {}
        self.forbidden_turns: set[tuple[str, str]] = set()
        self.uncertain_incoming_edges: set[str] = set()

    def add_edge(self, edge: RoadEdge) -> None:
        if edge.edge_id in self.edges:
            raise ValueError(f"Duplicate edge ID: {edge.edge_id}")
        if edge.length_m < 0:
            raise ValueError("Edge length cannot be negative")
        self.edges[edge.edge_id] = edge
        self.outgoing.setdefault(edge.from_node, []).append(edge)

    def forbid_turn(self, incoming_id: str, outgoing_id: str) -> None:
        incoming = self.edges[incoming_id]
        outgoing = self.edges[outgoing_id]
        if incoming.to_node != outgoing.from_node:
            raise ValueError("Restricted turn edges must meet")
        self.forbidden_turns.add((incoming_id, outgoing_id))

    def travel_time_s(self, edge: RoadEdge) -> float:
        speed = parse_maxspeed_kmh(edge.maxspeed)
        if speed is None:
            speed = self.speed_defaults_kmh.get(edge.highway)
        if speed is None or speed <= 0:
            raise ValueError(f"No usable speed for highway class {edge.highway}")
        return edge.length_m * 3.6 / speed

    def get_edge(self, edge_id: str) -> RoadEdge | None:
        return self.edges.get(edge_id)

    def iter_outgoing(self, node: str) -> list[RoadEdge]:
        return self.outgoing.get(node, [])

    def is_forbidden(self, incoming_id: str, outgoing_id: str) -> bool:
        return (incoming_id, outgoing_id) in self.forbidden_turns

    def is_turn_uncertain(self, incoming_id: str, outgoing_id: str) -> bool:
        return incoming_id in self.uncertain_incoming_edges


def parse_maxspeed_kmh(value: str | None) -> float | None:
    """Read simple OSM speed values; symbolic or ambiguous values use a class default."""
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(km/h|kmh|kph|mph)?\s*", value,
                         re.IGNORECASE)
    if not match:
        return None
    speed = float(match[1].replace(",", "."))
    if speed <= 0:
        return None
    return speed * 1.609344 if (match[2] or "").lower() == "mph" else speed


def validate_physical_path(graph: GraphLike, edge_ids: list[str], origin: str,
                           destination: str) -> PathResult:
    node = origin
    previous: str | None = None
    distance = time = 0.0
    for edge_id in edge_ids:
        edge = graph.get_edge(edge_id)
        if edge is None:
            return PathResult("INVALID", "UNKNOWN_EDGE", (), None, None)
        if edge.from_node != node:
            return PathResult("INVALID", "DISCONNECTED_OR_WRONG_DIRECTION", (), None, None)
        if previous is not None and graph.is_turn_uncertain(previous, edge_id):
            return PathResult("INDETERMINATE", "UNSUPPORTED_RESTRICTION", (), None, None)
        if previous is not None and graph.is_forbidden(previous, edge_id):
            return PathResult("INVALID", "PROHIBITED_TURN", (), None, None)
        node = edge.to_node
        previous = edge_id
        distance += edge.length_m
        time += graph.travel_time_s(edge)
    if node != destination:
        return PathResult("INVALID", "WRONG_DESTINATION", (), None, None)
    return PathResult("VALID", None, tuple(edge_ids), distance, time)


def validate_option(graph: GraphLike, origin: str, destination: str,
                    espacio_ids: tuple[int, ...], *, max_states: int = 500_000) -> PathResult:
    """Shortest legal path whose projected sequence equals the displayed sequence."""
    if not espacio_ids or any(a == b for a, b in itertools.pairwise(espacio_ids)):
        return PathResult("INVALID", "INVALID_DISPLAY_SEQUENCE", (), None, None)
    if max_states < 1:
        raise ValueError("max_states must be positive")
    # State includes the incoming edge so an OSM turn restriction can be checked.
    start: tuple[str, int, str | None] = (origin, 0, None)
    best: dict[tuple[str, int, str | None], float] = {start: 0.0}
    predecessor: dict[tuple[str, int, str | None], tuple[tuple[str, int, str | None], str]] = {}
    serial = itertools.count()
    queue: list[tuple[float, int, tuple[str, int, str | None]]] = [(0.0, next(serial), start)]
    visited = 0
    saw_uncertain_turn = False
    while queue:
        cost, _, state = heapq.heappop(queue)
        if cost > best[state]:
            continue
        visited += 1
        if visited > max_states:
            return PathResult("INDETERMINATE", "SEARCH_LIMIT", (), None, None)
        node, index, incoming_id = state
        if node == destination and index == len(espacio_ids):
            ids: list[str] = []
            cursor = state
            while cursor != start:
                cursor, edge_id = predecessor[cursor]
                ids.append(edge_id)
            ids.reverse()
            distance = 0.0
            for edge_id in ids:
                path_edge = graph.get_edge(edge_id)
                assert path_edge is not None
                distance += path_edge.length_m
            return PathResult("VALID", None, tuple(ids), distance, cost)
        for edge in graph.iter_outgoing(node):
            if incoming_id is not None and graph.is_turn_uncertain(incoming_id, edge.edge_id):
                saw_uncertain_turn = True
                continue
            if incoming_id is not None and graph.is_forbidden(incoming_id, edge.edge_id):
                continue
            next_index = _advance(espacio_ids, index, edge.espacio_id)
            if next_index is None:
                continue
            target = (edge.to_node, next_index, edge.edge_id)
            next_cost = cost + graph.travel_time_s(edge)
            if next_cost < best.get(target, float("inf")):
                best[target] = next_cost
                predecessor[target] = (state, edge.edge_id)
                heapq.heappush(queue, (next_cost, next(serial), target))
    if saw_uncertain_turn:
        return PathResult("INDETERMINATE", "UNSUPPORTED_RESTRICTION", (), None, None)
    return PathResult("INVALID", "NO_LEGAL_PATH", (), None, None)


def _advance(sequence: tuple[int, ...], index: int, espacio_id: int | None) -> int | None:
    if espacio_id is None:
        return index
    if index and espacio_id == sequence[index - 1]:
        return index
    if index < len(sequence) and espacio_id == sequence[index]:
        return index + 1
    return None
