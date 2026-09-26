"""Physical route projection and question-level quality checks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Edge:
    edge_id: str
    length_m: float
    espacio_id: int | None = None
    variant: str | None = None


@dataclass(frozen=True)
class Projection:
    espacio_ids: tuple[int, ...]
    variants: tuple[str | None, ...]
    hidden_distance_m: float
    hidden_ratio: float
    largest_hidden_gap_m: float


def project(edges: list[Edge]) -> Projection:
    if any(edge.length_m < 0 for edge in edges):
        raise ValueError("Edge length cannot be negative")
    ids: list[int] = []
    variants: list[str | None] = []
    hidden = gap = largest_gap = 0.0
    for edge in edges:
        if edge.espacio_id is None:
            hidden += edge.length_m
            gap += edge.length_m
        else:
            largest_gap = max(largest_gap, gap)
            gap = 0.0
            if not ids or ids[-1] != edge.espacio_id:
                ids.append(edge.espacio_id)
                variants.append(edge.variant)
    largest_gap = max(largest_gap, gap)
    total = sum(edge.length_m for edge in edges)
    return Projection(tuple(ids), tuple(variants), hidden, hidden / total if total else 0,
                      largest_gap)


@dataclass(frozen=True)
class Option:
    letter: str
    espacio_ids: tuple[int, ...]
    is_valid: bool
    estimated_time_s: float | None = None


@dataclass(frozen=True)
class QuestionCheck:
    accepted: bool
    correct_option: str | None
    reason: str | None


def check_question(
    question_type: str,
    options: list[Option],
    *,
    minimum_espacios: int = 6,
    min_advantage_ratio: float = 0.05,
    min_advantage_seconds: float = 30,
) -> QuestionCheck:
    if sorted(option.letter for option in options) != ["A", "B", "C"]:
        return QuestionCheck(False, None, "REQUIRES_THREE_OPTIONS")
    if any(len(option.espacio_ids) < minimum_espacios for option in options):
        return QuestionCheck(False, None, "TOO_FEW_ESPACIOS")
    if len({option.espacio_ids for option in options}) != 3:
        return QuestionCheck(False, None, "DUPLICATE_OPTIONS")
    valid = [option for option in options if option.is_valid]
    if question_type == "VALID_ROUTE":
        if len(valid) != 1:
            return QuestionCheck(False, None, "VALID_OPTION_COUNT")
        return QuestionCheck(True, valid[0].letter, None)
    if question_type == "FASTEST_ROUTE":
        if len(valid) != 3:
            return QuestionCheck(False, None, "INVALID_FASTEST_OPTION")
        if any(option.estimated_time_s is None or option.estimated_time_s <= 0
               for option in options):
            return QuestionCheck(False, None, "MISSING_ROUTE_TIME")
        ranked = sorted(options, key=lambda option: option.estimated_time_s or 0)
        winner, runner_up = ranked[:2]
        advantage = (runner_up.estimated_time_s or 0) - (winner.estimated_time_s or 0)
        if advantage < min_advantage_seconds or advantage / (winner.estimated_time_s or 1) < min_advantage_ratio:
            return QuestionCheck(False, None, "AMBIGUOUS_FASTEST_ROUTE")
        return QuestionCheck(True, winner.letter, None)
    return QuestionCheck(False, None, "UNKNOWN_QUESTION_TYPE")
