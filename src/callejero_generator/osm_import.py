"""Stream a Madrid OSM PBF into a compact directed SQLite driving graph."""

import json
import math
import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from itertools import pairwise
from pathlib import Path

import osmium  # type: ignore[import-untyped]

from .normalization import normalize_name

GRAPH_SCHEMA = files("callejero_generator").joinpath("schema/osm_graph_schema.sql")
_BLOCKED_ACCESS = {"no", "private", "agricultural", "forestry", "delivery",
                   "permit", "destination", "customers", "official", "emergency"}


@dataclass(frozen=True)
class Restriction:
    relation_id: int
    kind: str
    members: tuple[tuple[str, str, int], ...]
    conditional: bool = False


@dataclass(frozen=True)
class GraphBuildReport:
    nodes: int
    directed_edges: int
    mapped_edges: int
    forbidden_turns: int
    unsupported_restrictions: int
    missing_location_segments: int
    pbf_sha256: str


def is_drivable(tags: dict[str, str], speed_defaults: dict[str, float]) -> bool:
    highway = tags.get("highway", "")
    if highway not in speed_defaults or tags.get("area") == "yes":
        return False
    if any(key in tags for key in ("motorcar:conditional", "motor_vehicle:conditional",
                                   "vehicle:conditional", "access:conditional")):
        return False
    for key in ("motorcar", "motor_vehicle", "vehicle", "access"):
        if key in tags:
            return tags[key] not in _BLOCKED_ACCESS
    return True


def allowed_directions(tags: dict[str, str]) -> tuple[bool, bool]:
    value = (tags.get("oneway:motorcar") or tags.get("oneway:motor_vehicle")
             or tags.get("oneway:vehicle") or tags.get("oneway") or "").lower()
    if value in {"yes", "true", "1"}:
        return True, False
    if value == "-1":
        return False, True
    if value in {"no", "false", "0"}:
        return True, True
    if tags.get("junction") == "roundabout" or tags.get("highway") == "motorway":
        return True, False
    return True, True


def segment_length_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2
    a += (math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
          * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))


class _NameMap:
    def __init__(self, generator_db: sqlite3.Connection):
        self.exact: dict[str, int | None] = {}
        self.normalized: dict[str, int | None] = {}
        for row in generator_db.execute(
            "SELECT id, canonical_name, normalized_name FROM espacios WHERE active=1"
        ):
            self.exact[row["canonical_name"]] = row["id"]
            self._add(self.normalized, row["normalized_name"], row["id"])
        for row in generator_db.execute(
            """SELECT a.alias, a.normalized_alias, a.espacio_id FROM espacio_aliases a
               JOIN espacios e ON e.id=a.espacio_id
               WHERE a.manually_approved=1 AND e.active=1"""
        ):
            self._add(self.exact, row["alias"], row["espacio_id"])
            self._add(self.normalized, row["normalized_alias"], row["espacio_id"])
        self.overrides: dict[int, int | None] = {}
        for row in generator_db.execute(
            """SELECT osm_object_id, espacio_id FROM osm_espacio_mapping
               WHERE osm_object_type='way' AND manually_approved=1"""
        ):
            self._add(self.overrides, int(row["osm_object_id"]), row["espacio_id"])
        self.cache: dict[str, int | None] = {}

    @staticmethod
    def _add(mapping: dict, key: str | int, value: int) -> None:
        if key in mapping and mapping[key] != value:
            mapping[key] = None
        else:
            mapping[key] = value

    def resolve(self, way_id: int, name: str) -> int | None:
        if way_id in self.overrides:
            return self.overrides[way_id]
        if name not in self.cache:
            self.cache[name] = self.exact.get(name)
            if self.cache[name] is None and name not in self.exact:
                self.cache[name] = self.normalized.get(normalize_name(name))
        return self.cache[name]


class _ImportHandler(osmium.SimpleHandler):
    def __init__(self, database: sqlite3.Connection, names: _NameMap,
                 speed_defaults: dict[str, float]):
        super().__init__()
        self.db = database
        self.names = names
        self.speed_defaults = speed_defaults
        self.node_batch: list[tuple[int, float, float]] = []
        self.edge_batch: list[tuple] = []
        self.restrictions: list[Restriction] = []
        self.directed_edges = 0
        self.mapped_edges = 0
        self.missing_location_segments = 0

    def way(self, way) -> None:
        tags = dict(way.tags)
        if not is_drivable(tags, self.speed_defaults):
            return
        way_id = int(way.id)
        name = tags.get("name", "")
        espacio_id = self.names.resolve(way_id, name) if name or way_id in self.names.overrides else None
        forward, backward = allowed_directions(tags)
        nodes = list(way.nodes)
        for index, (start, end) in enumerate(pairwise(nodes)):
            if not start.location.valid() or not end.location.valid():
                self.missing_location_segments += 1
                continue
            lat1, lon1 = start.location.lat, start.location.lon
            lat2, lon2 = end.location.lat, end.location.lon
            length = segment_length_m(lat1, lon1, lat2, lon2)
            if length <= 0:
                continue
            self.node_batch.extend(((int(start.ref), lat1, lon1), (int(end.ref), lat2, lon2)))
            if forward:
                self.edge_batch.append((f"{way_id}:{index}:F", way_id, int(start.ref), int(end.ref),
                                        length, tags["highway"], tags.get("maxspeed:forward")
                                        or tags.get("maxspeed"), name or None, tags.get("ref"), espacio_id))
            if backward:
                self.edge_batch.append((f"{way_id}:{index}:R", way_id, int(end.ref), int(start.ref),
                                        length, tags["highway"], tags.get("maxspeed:backward")
                                        or tags.get("maxspeed"), name or None, tags.get("ref"), espacio_id))
            if len(self.edge_batch) >= 20_000:
                self.flush()

    def relation(self, relation) -> None:
        if relation.tags.get("type", "") not in {
            "restriction", "restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle"
        }:
            return
        except_modes = {mode.strip() for mode in
                        (relation.tags.get("except") or "").replace(",", ";").split(";")}
        if except_modes & {"motorcar", "motor_vehicle", "vehicle", "car"}:
            return
        kind = relation.tags.get("restriction:motorcar") or relation.tags.get("restriction") or ""
        conditional = bool(relation.tags.get("restriction:conditional")
                           or relation.tags.get("restriction:motorcar:conditional"))
        members = tuple((member.type, member.role, int(member.ref))
                        for member in relation.members)
        self.restrictions.append(Restriction(int(relation.id), kind, members, conditional))

    def flush(self) -> None:
        if not self.edge_batch:
            return
        self.db.executemany(
            "INSERT OR IGNORE INTO nodes (node_id, latitude, longitude) VALUES (?, ?, ?)",
            self.node_batch,
        )
        self.db.executemany(
            """INSERT INTO edges (edge_id, way_id, from_node, to_node, length_m,
               highway, maxspeed, osm_name, osm_ref, espacio_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            self.edge_batch,
        )
        self.directed_edges += len(self.edge_batch)
        self.mapped_edges += sum(row[-1] is not None for row in self.edge_batch)
        self.node_batch.clear()
        self.edge_batch.clear()
        self.db.commit()


def _materialize_restrictions(database: sqlite3.Connection,
                              relations: list[Restriction]) -> int:
    count = 0
    for relation in relations:
        from_ways = [ref for typ, role, ref in relation.members if typ == "w" and role == "from"]
        to_ways = [ref for typ, role, ref in relation.members if typ == "w" and role == "to"]
        via_nodes = [ref for typ, role, ref in relation.members if typ == "n" and role == "via"]
        via_ways = [ref for typ, role, ref in relation.members if typ == "w" and role == "via"]
        reason = None
        if relation.conditional and not relation.kind:
            reason = "CONDITIONAL"
        elif via_ways:
            reason = "VIA_WAY"
        elif len(via_nodes) != 1 or not from_ways or not to_ways:
            reason = "UNSUPPORTED_MEMBERS"
        elif not relation.kind.startswith(("no_", "only_")):
            reason = "UNKNOWN_RESTRICTION"
        if reason:
            database.execute(
                """INSERT INTO unsupported_restrictions
                   (relation_id, restriction, reason, affected_way_ids_json,
                    affected_via_nodes_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (relation.relation_id, relation.kind, reason, json.dumps(from_ways),
                 json.dumps(via_nodes)),
            )
            continue
        via = via_nodes[0]
        incoming = database.execute(
            f"""SELECT edge_id FROM edges WHERE to_node=? AND way_id IN
                ({','.join('?' for _ in from_ways)})""", (via, *from_ways)
        ).fetchall()
        if relation.kind.startswith("only_"):
            outgoing = database.execute(
                f"""SELECT edge_id FROM edges WHERE from_node=? AND way_id NOT IN
                    ({','.join('?' for _ in to_ways)})""", (via, *to_ways)
            ).fetchall()
        else:
            outgoing = database.execute(
                f"""SELECT edge_id FROM edges WHERE from_node=? AND way_id IN
                    ({','.join('?' for _ in to_ways)})""", (via, *to_ways)
            ).fetchall()
        pairs = [(a[0], b[0], relation.relation_id) for a in incoming for b in outgoing]
        database.executemany(
            "INSERT OR IGNORE INTO forbidden_turns VALUES (?, ?, ?)", pairs
        )
        count += len(pairs)
    database.commit()
    return count


def build_osm_graph(pbf_path: str | Path, generator_db: sqlite3.Connection,
                    output_path: str | Path, speed_defaults: dict[str, float],
                    *, source_url: str = "", snapshot_date: str = "",
                    expected_sha256: str | None = None) -> GraphBuildReport:
    pbf = Path(pbf_path)
    digest = sha256(pbf.read_bytes()).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError("PBF hash does not match the pinned configuration")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temporary) as database:
            database.execute("PRAGMA synchronous=OFF")
            database.executescript(GRAPH_SCHEMA.read_text(encoding="utf-8"))
            handler = _ImportHandler(database, _NameMap(generator_db), speed_defaults)
            handler.apply_file(str(pbf), locations=True)
            handler.flush()
            database.executescript("""
                CREATE INDEX idx_edges_from ON edges(from_node);
                CREATE INDEX idx_edges_to_way ON edges(to_node, way_id);
                CREATE INDEX idx_edges_way_from ON edges(way_id, from_node);
            """)
            forbidden = _materialize_restrictions(database, handler.restrictions)
            database.execute("CREATE INDEX idx_turn_incoming ON forbidden_turns(incoming_edge_id)")
            nodes = database.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            unsupported = database.execute("SELECT COUNT(*) FROM unsupported_restrictions").fetchone()[0]
            metadata = {
                "pbf_sha256": digest,
                "pbf_filename": pbf.name,
                "source_url": source_url,
                "snapshot_date": snapshot_date,
                "nodes": str(nodes),
                "directed_edges": str(handler.directed_edges),
                "mapped_edges": str(handler.mapped_edges),
                "forbidden_turns": str(forbidden),
                "unsupported_restrictions": str(unsupported),
            }
            database.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
            database.commit()
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return GraphBuildReport(nodes, handler.directed_edges, handler.mapped_edges,
                            forbidden, unsupported, handler.missing_location_segments, digest)
