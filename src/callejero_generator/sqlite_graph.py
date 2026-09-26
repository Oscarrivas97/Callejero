"""Lazy graph adapter over the imported Madrid SQLite road graph."""

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Self

from .road_graph import RoadEdge, parse_maxspeed_kmh


class SQLiteRoadGraph:
    def __init__(self, path: str | Path, speed_defaults_kmh: dict[str, float]):
        self.connection = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.speed_defaults_kmh = speed_defaults_kmh
        self.uncertain_way_ids = {
            int(way_id)
            for row in self.connection.execute(
                "SELECT affected_way_ids_json FROM unsupported_restrictions"
            )
            for way_id in json.loads(row[0])
        }
        self._edge_cached = lru_cache(maxsize=200_000)(self._query_edge)
        self._outgoing_cached = lru_cache(maxsize=100_000)(self._query_outgoing)
        self._forbidden_cached = lru_cache(maxsize=200_000)(self._query_forbidden)

    def close(self) -> None:
        self._edge_cached.cache_clear()
        self._outgoing_cached.cache_clear()
        self._forbidden_cached.cache_clear()
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _edge(row: sqlite3.Row) -> RoadEdge:
        return RoadEdge(row["edge_id"], str(row["from_node"]), str(row["to_node"]),
                        row["length_m"], row["highway"], row["maxspeed"], row["espacio_id"])

    def get_edge(self, edge_id: str) -> RoadEdge | None:
        return self._edge_cached(edge_id)

    def _query_edge(self, edge_id: str) -> RoadEdge | None:
        row = self.connection.execute("SELECT * FROM edges WHERE edge_id=?", (edge_id,)).fetchone()
        return self._edge(row) if row is not None else None

    def iter_outgoing(self, node: str) -> list[RoadEdge]:
        return self._outgoing_cached(node)

    def _query_outgoing(self, node: str) -> list[RoadEdge]:
        rows = self.connection.execute(
            "SELECT * FROM edges WHERE from_node=? ORDER BY edge_id", (int(node),)
        ).fetchall()
        return [self._edge(row) for row in rows]

    def is_forbidden(self, incoming_id: str, outgoing_id: str) -> bool:
        return self._forbidden_cached(incoming_id, outgoing_id)

    def _query_forbidden(self, incoming_id: str, outgoing_id: str) -> bool:
        return self.connection.execute(
            """SELECT 1 FROM forbidden_turns WHERE incoming_edge_id=?
               AND outgoing_edge_id=? LIMIT 1""", (incoming_id, outgoing_id)
        ).fetchone() is not None

    def is_turn_uncertain(self, incoming_id: str, outgoing_id: str) -> bool:
        if not self.uncertain_way_ids:
            return False
        incoming_way = int(incoming_id.split(":", 1)[0])
        outgoing_way = int(outgoing_id.split(":", 1)[0])
        return incoming_way in self.uncertain_way_ids and incoming_way != outgoing_way

    def travel_time_s(self, edge: RoadEdge) -> float:
        speed = parse_maxspeed_kmh(edge.maxspeed) or self.speed_defaults_kmh.get(edge.highway)
        if speed is None or speed <= 0:
            raise ValueError(f"No usable speed for highway class {edge.highway}")
        return edge.length_m * 3.6 / speed
