"""Question validation backed by legal constrained paths."""

from dataclasses import dataclass

from .road_graph import GraphLike, PathResult, validate_option
from .routes import Option, QuestionCheck, check_question
from .settings import QualitySettings


@dataclass(frozen=True)
class ValidatedQuestion:
    check: QuestionCheck
    option_paths: dict[str, PathResult]


def validate_question_on_graph(
    graph: GraphLike,
    origin: str,
    destination: str,
    question_type: str,
    options: dict[str, tuple[int, ...]],
    settings: QualitySettings,
    *,
    max_states: int = 500_000,
) -> ValidatedQuestion:
    paths = {letter: validate_option(graph, origin, destination, sequence,
                                     max_states=max_states)
             for letter, sequence in options.items()}
    if any(path.status == "INDETERMINATE" for path in paths.values()):
        return ValidatedQuestion(QuestionCheck(False, None, "INDETERMINATE_OPTION"), paths)
    check = check_question(
        question_type,
        [Option(letter, sequence, paths[letter].status == "VALID",
                paths[letter].estimated_time_s)
         for letter, sequence in options.items()],
        minimum_espacios=settings.minimum_espacios,
        min_advantage_ratio=settings.min_advantage_ratio,
        min_advantage_seconds=settings.min_advantage_seconds,
    )
    return ValidatedQuestion(check, paths)
