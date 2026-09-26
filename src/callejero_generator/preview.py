"""Generate inspectable, unapproved Hito-to-Hito VALID_ROUTE questions."""

import json
import random
import sqlite3
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import pairwise
from pathlib import Path

import yaml

from .osm_import import segment_length_m
from .road_graph import GraphLike, shortest_physical_route, validate_option, validate_physical_path
from .routes import Edge, project
from .settings import QualitySettings
from .sqlite_graph import SQLiteRoadGraph
from .validation import validate_question_on_graph


@dataclass(frozen=True)
class PreviewQuestion:
    origin_hito_id: int
    destination_hito_id: int
    origin: str
    destination: str
    origin_node: str
    destination_node: str
    wording: str
    difficulty: str
    options: dict[str, tuple[int, ...]]
    correct_option: str
    option_status: dict[str, str]
    physical_edge_ids: tuple[str, ...]
    distance_m: float
    estimated_time_s: float
    hidden_ratio: float
    origin_snap_m: float
    destination_snap_m: float


def _mutation_indices(length: int) -> list[int]:
    indexes = list(range(1, length - 2))
    targets = (length // 3, 2 * length // 3)
    return sorted(indexes, key=lambda index: (min(abs(index - t) for t in targets), index))


def build_preview_question(
    graph: GraphLike,
    *,
    origin_id: int,
    destination_id: int,
    origin_name: str,
    destination_name: str,
    origin_node: str,
    destination_node: str,
    origin_snap_m: float,
    destination_snap_m: float,
    quality: QualitySettings,
    max_hidden_ratio: float,
    easy_max: int,
    medium_max: int,
    random_seed: int,
    max_states: int = 150_000,
) -> PreviewQuestion | None:
    route = shortest_physical_route(graph, origin_node, destination_node,
                                    max_states=max_states)
    if route.status != "VALID" or route.distance_m is None or route.estimated_time_s is None:
        return None
    if validate_physical_path(graph, list(route.edge_ids), origin_node,
                              destination_node).status != "VALID":
        return None
    physical_edges = []
    for edge_id in route.edge_ids:
        edge = graph.get_edge(edge_id)
        assert edge is not None
        physical_edges.append(Edge(edge_id, edge.length_m, edge.espacio_id))
    projection = project(physical_edges)
    correct = projection.espacio_ids
    if len(correct) < quality.minimum_espacios or projection.hidden_ratio > max_hidden_ratio:
        return None
    if validate_option(graph, origin_node, destination_node, correct,
                       max_states=max_states).status != "VALID":
        return None

    distractors: list[tuple[int, ...]] = []
    used_indices: list[int] = []
    for index in _mutation_indices(len(correct)):
        if used_indices and min(abs(index - used) for used in used_indices) < 2:
            continue
        mutated = list(correct)
        mutated[index], mutated[index + 1] = mutated[index + 1], mutated[index]
        candidate = tuple(mutated)
        if candidate == correct or candidate in distractors:
            continue
        if any(a == b for a, b in pairwise(candidate)):
            continue
        outcome = validate_option(graph, origin_node, destination_node, candidate,
                                  max_states=max_states)
        if outcome.status == "INVALID":
            distractors.append(candidate)
            used_indices.append(index)
        if len(distractors) == 2:
            break
    if len(distractors) != 2:
        return None

    sequences = [correct, *distractors]
    random.Random(random_seed + origin_id * 1000 + destination_id).shuffle(sequences)
    options = dict(zip("ABC", sequences))
    checked = validate_question_on_graph(
        graph, origin_node, destination_node, "VALID_ROUTE", options, quality,
        max_states=max_states,
    )
    if not checked.check.accepted or checked.check.correct_option is None:
        return None
    difficulty = "EASY" if len(correct) <= easy_max else (
        "MEDIUM" if len(correct) <= medium_max else "HARD"
    )
    wording = (f"¿Qué recorrido es correcto para ir del hito {origin_name} "
               f"al hito {destination_name} siguiendo las normas de circulación ordinarias?")
    return PreviewQuestion(
        origin_id, destination_id, origin_name, destination_name, origin_node,
        destination_node, wording, difficulty, options, checked.check.correct_option,
        {letter: outcome.status for letter, outcome in checked.option_paths.items()},
        route.edge_ids, route.distance_m, route.estimated_time_s,
        projection.hidden_ratio, origin_snap_m, destination_snap_m,
    )


def write_preview(
    generator_db: sqlite3.Connection,
    graph: SQLiteRoadGraph,
    graph_metadata: dict[str, str],
    seed_path: str | Path,
    config_path: str | Path,
    output_prefix: str | Path,
) -> list[PreviewQuestion]:
    seed = yaml.safe_load(Path(seed_path).read_text(encoding="utf-8"))
    config_bytes = Path(config_path).read_bytes()
    config = yaml.safe_load(config_bytes)
    if graph_metadata["pbf_sha256"] != config["osm"]["sha256"]:
        raise ValueError("Preview attachments require the pinned Madrid graph")
    quality = QualitySettings(
        int(config["projection"]["minimum_displayed_espacios"]),
        float(config["fastest_route"]["min_advantage_ratio"]),
        float(config["fastest_route"]["min_advantage_seconds"]),
    )
    max_snap_m = float(seed.get("max_snap_m", 100))
    hitos = {}
    for name, attachment in seed["hitos"].items():
        hito = generator_db.execute(
            "SELECT id, source_address FROM hitos WHERE canonical_name=?", (name,)
        ).fetchone()
        if hito is None:
            raise ValueError(f"Unknown Hito: {name}")
        node = str(attachment["road_node"])
        coords = graph.node_coordinates(node)
        if coords is None:
            raise ValueError(f"Unknown road node for {name}: {node}")
        snap_distance = segment_length_m(
            float(attachment["latitude"]), float(attachment["longitude"]), *coords
        )
        if snap_distance > max_snap_m:
            raise ValueError(f"Road node for {name} is {snap_distance:.0f} m from POI")
        hitos[name] = (hito["id"], node, snap_distance)

    questions = []
    for origin_name, destination_name in seed["pairs"]:
        origin_id, origin_node, origin_snap = hitos[origin_name]
        destination_id, destination_node, destination_snap = hitos[destination_name]
        question = build_preview_question(
            graph, origin_id=origin_id, destination_id=destination_id,
            origin_name=origin_name, destination_name=destination_name,
            origin_node=origin_node, destination_node=destination_node,
            origin_snap_m=origin_snap, destination_snap_m=destination_snap,
            quality=quality,
            max_hidden_ratio=float(config["projection"]["max_hidden_distance_ratio"]),
            easy_max=int(config["difficulty"]["easy"]["max_espacios"]),
            medium_max=int(config["difficulty"]["medium"]["max_espacios"]),
            random_seed=int(config["generation"]["random_seed"]),
        )
        if question is None:
            raise ValueError(f"No fully validated preview question for {origin_name} → {destination_name}")
        questions.append(question)

    all_ids = {item for question in questions for sequence in question.options.values()
               for item in sequence}
    placeholders = ",".join("?" for _ in all_ids)
    names = {row["id"]: row["canonical_name"] for row in generator_db.execute(
        f"SELECT id, canonical_name FROM espacios WHERE active=1 AND id IN ({placeholders})",
        tuple(all_ids),
    )} if all_ids else {}
    if len(names) != len(all_ids):
        raise ValueError("Preview contains an unknown canonical Espacio")

    output = Path(output_prefix)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PROVISIONAL_PREVIEW",
        "osm_sha256": graph_metadata["pbf_sha256"],
        "config_sha256": sha256(config_bytes).hexdigest(),
        "attachments": seed["hitos"],
        "questions": [asdict(question) for question in questions],
    }
    output.with_suffix(".json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# Callejero question preview", "",
             "Provisional Hito road attachments. These questions have not been manually approved.", "",
             f"OSM SHA-256: `{graph_metadata['pbf_sha256']}`", ""]
    for number, question in enumerate(questions, 1):
        lines.extend([f"## {number}. {question.origin} → {question.destination}", "",
                      question.wording, ""])
        for letter, sequence in question.options.items():
            lines.append(f"**{letter})** {' → '.join(names[item] for item in sequence)}")
            lines.append("")
        lines.extend([
            (f"**Respuesta:** {question.correct_option} · **Dificultad:** {question.difficulty} · "
             f"**Validez:** {', '.join(f'{key}={value}' for key, value in question.option_status.items())}"),
            "",
            (f"Physical route: {question.distance_m:.0f} m, {question.estimated_time_s:.0f} s; "
             f"hidden distance {question.hidden_ratio:.1%}; "
             f"Hito snap offsets {question.origin_snap_m:.0f} m / {question.destination_snap_m:.0f} m."),
            "",
        ])
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    return questions
