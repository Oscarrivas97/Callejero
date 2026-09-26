from callejero_generator.road_graph import (
    RoadEdge,
    RoadGraph,
    parse_maxspeed_kmh,
    validate_option,
    validate_physical_path,
)
from callejero_generator.settings import QualitySettings
from callejero_generator.validation import validate_question_on_graph


def _graph():
    graph = RoadGraph({"residential": 30})
    for edge in [RoadEdge("a", "o", "x", 100, "residential", espacio_id=1),
                 RoadEdge("b", "x", "y", 100, "residential", espacio_id=2),
                 RoadEdge("c", "y", "d", 100, "residential", espacio_id=3),
                 RoadEdge("reverse", "y", "x", 100, "residential", espacio_id=2)]:
        graph.add_edge(edge)
    return graph


def test_direction_turns_and_exact_projection():
    graph = _graph()
    assert validate_physical_path(graph, ["a", "b", "c"], "o", "d").status == "VALID"
    assert validate_physical_path(graph, ["a", "reverse", "c"], "o", "d").reason == "DISCONNECTED_OR_WRONG_DIRECTION"
    assert validate_option(graph, "o", "d", (1, 2, 3)).edge_ids == ("a", "b", "c")
    assert validate_option(graph, "o", "d", (1, 3)).reason == "NO_LEGAL_PATH"
    graph.forbid_turn("a", "b")
    assert validate_physical_path(graph, ["a", "b", "c"], "o", "d").reason == "PROHIBITED_TURN"
    assert validate_option(graph, "o", "d", (1, 2, 3)).reason == "NO_LEGAL_PATH"


def test_hidden_edges_and_search_limit():
    graph = RoadGraph({"residential": 30})
    graph.add_edge(RoadEdge("a", "o", "x", 100, "residential", espacio_id=1))
    graph.add_edge(RoadEdge("hidden", "x", "y", 200, "residential"))
    graph.add_edge(RoadEdge("b", "y", "d", 100, "residential", espacio_id=2))
    assert validate_option(graph, "o", "d", (1, 2)).edge_ids == ("a", "hidden", "b")
    assert validate_option(graph, "o", "d", (1, 2), max_states=1).status == "INDETERMINATE"


def test_fastest_question_uses_constrained_path_costs():
    graph = RoadGraph({"residential": 30})
    for index, length in enumerate((100, 200, 300), 1):
        graph.add_edge(RoadEdge(str(index), "o", "d", length, "residential",
                                espacio_id=index))
    checked = validate_question_on_graph(
        graph, "o", "d", "FASTEST_ROUTE",
        {"A": (1,), "B": (2,), "C": (3,)}, QualitySettings(1, 0.05, 5),
    )
    assert checked.check.accepted
    assert checked.check.correct_option == "A"
    assert checked.option_paths["A"].estimated_time_s == 12


def test_speed_parsing_and_fallback():
    assert parse_maxspeed_kmh("50 km/h") == 50
    assert round(parse_maxspeed_kmh("30 mph") or 0, 2) == 48.28
    assert parse_maxspeed_kmh("ES:urban") is None
    graph = RoadGraph({"residential": 30})
    assert graph.travel_time_s(RoadEdge("a", "o", "d", 100, "residential", "bad")) == 12
