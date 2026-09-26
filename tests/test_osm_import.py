import sqlite3

from callejero_generator.db import connect, init_db
from callejero_generator.osm_import import allowed_directions, build_osm_graph, is_drivable
from callejero_generator.road_graph import validate_option, validate_physical_path
from callejero_generator.sqlite_graph import SQLiteRoadGraph


def test_osm_access_and_direction_rules():
    speeds = {"residential": 30, "motorway": 100}
    assert not is_drivable({"highway": "footway"}, speeds)
    assert not is_drivable({"highway": "residential", "motorcar": "private"}, speeds)
    assert not is_drivable({"highway": "residential", "access": "destination"}, speeds)
    assert is_drivable({"highway": "residential", "access": "private", "motorcar": "yes"}, speeds)
    assert not is_drivable({"highway": "residential", "motorcar:conditional": "yes @ (Mo-Fr)"}, speeds)
    assert allowed_directions({"oneway": "-1"}) == (False, True)
    assert allowed_directions({"highway": "motorway"}) == (True, False)
    assert allowed_directions({"junction": "roundabout", "oneway": "no"}) == (True, True)


def test_osm_xml_build_connects_sqlite_validator(tmp_path):
    source = tmp_path / "toy.osm"
    source.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
  <node id="1" lat="40.0" lon="-3.0" version="1"/>
  <node id="2" lat="40.0" lon="-2.999" version="1"/>
  <node id="3" lat="40.0" lon="-2.998" version="1"/>
  <node id="4" lat="40.001" lon="-2.999" version="1"/>
  <way id="10" version="1"><nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="residential"/><tag k="name" v="Calle A"/>
    <tag k="oneway" v="yes"/></way>
  <way id="20" version="1"><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="residential"/><tag k="name" v="Calle B"/></way>
  <way id="30" version="1"><nd ref="2"/><nd ref="4"/>
    <tag k="highway" v="residential"/><tag k="name" v="Calle C"/></way>
  <way id="40" version="1"><nd ref="4"/><nd ref="3"/>
    <tag k="highway" v="residential"/><tag k="name" v="Calle D"/></way>
  <relation id="100" version="1"><member type="way" ref="10" role="from"/>
    <member type="node" ref="2" role="via"/>
    <member type="way" ref="20" role="to"/>
    <tag k="type" v="restriction"/><tag k="restriction" v="no_left_turn"/></relation>
</osm>""", encoding="utf-8")
    generator = tmp_path / "generator.sqlite"
    graph_path = tmp_path / "graph.sqlite"
    init_db(generator)
    with connect(generator) as db:
        for index, name in enumerate(("Calle A", "Calle B", "Calle C", "Calle D"), 1):
            db.execute("INSERT INTO espacios (id, canonical_name, normalized_name) VALUES (?, ?, ?)",
                       (index, name, name.casefold()))
        report = build_osm_graph(source, db, graph_path, {"residential": 30})
    assert report.nodes == 4
    assert report.directed_edges == 7
    assert report.mapped_edges == 7
    assert report.forbidden_turns == 1
    assert report.unsupported_restrictions == 0
    with SQLiteRoadGraph(graph_path, {"residential": 30}) as graph:
        assert validate_physical_path(graph, ["10:0:F", "20:0:F"], "1", "3").reason == "PROHIBITED_TURN"
        assert validate_option(graph, "1", "3", (1, 2)).reason == "NO_LEGAL_PATH"
        assert validate_option(graph, "1", "3", (1, 3, 4)).edge_ids == (
            "10:0:F", "30:0:F", "40:0:F"
        )
        assert validate_physical_path(graph, ["10:0:R"], "2", "1").reason == "UNKNOWN_EDGE"
    with sqlite3.connect(graph_path) as db:
        assert db.execute("SELECT value FROM metadata WHERE key='pbf_sha256'").fetchone()[0]
        db.execute("""INSERT INTO unsupported_restrictions
                    (relation_id, restriction, reason, affected_way_ids_json)
                    VALUES (200, 'no_right_turn', 'VIA_WAY', '[10]')""")
    with SQLiteRoadGraph(graph_path, {"residential": 30}) as graph:
        assert validate_option(graph, "1", "3", (1, 3, 4)).status == "INDETERMINATE"
