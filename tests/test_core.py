import csv
import json
import sqlite3
from pathlib import Path

import pytest

from callejero_generator.db import connect, init_db
from callejero_generator.importers import import_espacios, import_hitos
from callejero_generator.normalization import normalize_name
from callejero_generator.resolution import approve_alias, resolve
from callejero_generator.review import export_approved, review_question
from callejero_generator.routes import Edge, Option, check_question, project
from callejero_generator.settings import load_quality_settings, load_speed_defaults


def test_packaged_schemas_match_documented_schemas():
    root = Path(__file__).resolve().parents[1]
    for name in ("generator_schema.sql", "app_export_schema.sql"):
        assert (root / "sql" / name).read_bytes() == (
            root / "src" / "callejero_generator" / "schema" / name
        ).read_bytes()


def test_example_quality_configuration():
    path = Path(__file__).resolve().parents[1] / "config" / "generator.example.yaml"
    settings = load_quality_settings(path)
    assert settings.minimum_espacios == 6
    assert settings.min_advantage_ratio == 0.05
    assert settings.min_advantage_seconds == 30
    assert load_speed_defaults(path)["motorway"] == 100


def _csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def test_normalization_and_ambiguous_lookup(tmp_path):
    assert normalize_name("Av. de América") == normalize_name("Avenida de America")
    assert normalize_name("C/ Mayor") == normalize_name("Calle Mayor")
    database = tmp_path / "generator.sqlite"
    init_db(database)
    source = tmp_path / "espacios.csv"
    _csv(source, ["canonical_name"], [["Av. de América"], ["Avenida de America"]])
    with connect(database) as connection:
        import_espacios(connection, source)
        assert resolve(connection, "Av. de América").method == "canonical_exact"
        assert resolve(connection, "AV DE AMERICA").method == "ambiguous"


def test_import_preserves_hito_review_and_alias(tmp_path):
    database = tmp_path / "generator.sqlite"
    init_db(database)
    espacios = tmp_path / "espacios.csv"
    hitos = tmp_path / "hitos.csv"
    _csv(espacios, ["canonical_name"], [["Paseo de la Castellana"]])
    _csv(hitos, ["canonical_name", "source_address"], [["Hito A", "Calle Mayor 1"]])
    with connect(database) as connection:
        import_espacios(connection, espacios)
        import_hitos(connection, hitos)
        connection.execute("UPDATE hitos SET review_status='APPROVED', latitude=40 WHERE id=1")
        import_hitos(connection, hitos)
        assert connection.execute("SELECT review_status FROM hitos").fetchone()[0] == "APPROVED"
        approve_alias(connection, 1, "Pº de la Castellana")
        assert resolve(connection, "Pº de la Castellana").espacio_id == 1


def test_projection_and_question_rules():
    result = project([Edge("1", 100, 1), Edge("2", 50, 1), Edge("3", 30),
                      Edge("4", 70, 2), Edge("5", 50, 1)])
    assert result.espacio_ids == (1, 2, 1)
    assert result.hidden_ratio == 0.1
    assert result.largest_hidden_gap_m == 30
    options = [Option("A", (1, 2, 3, 4, 5, 6), True, 500),
               Option("B", (1, 2, 3, 4, 5, 7), True, 560),
               Option("C", (1, 2, 3, 4, 5, 8), True, 600)]
    assert check_question("FASTEST_ROUTE", options).correct_option == "A"
    assert check_question("VALID_ROUTE", options).reason == "VALID_OPTION_COUNT"
    assert check_question("FASTEST_ROUTE", [options[0], Option("B", options[1].espacio_ids,
                                                                 True, 520), options[2]]).reason == "AMBIGUOUS_FASTEST_ROUTE"


def test_export_requires_review_and_canonicalizes_names(tmp_path):
    source = tmp_path / "generator.sqlite"
    target = tmp_path / "app.sqlite"
    init_db(source)
    with connect(source) as db:
        db.execute("INSERT INTO generator_runs (id) VALUES (1)")
        for index in range(1, 9):
            db.execute("INSERT INTO espacios (id, canonical_name, normalized_name) VALUES (?, ?, ?)",
                       (index, f"Calle {index}", f"calle {index}"))
        for index in (1, 2):
            db.execute("INSERT INTO hitos (id, canonical_name, source_address) VALUES (?, ?, ?)",
                       (index, f"Hito {index}", f"Address {index}"))
        db.execute("""INSERT INTO questions (id, generator_run_id, question_type,
                    origin_hito_id, destination_hito_id, wording, difficulty, correct_option,
                    status) VALUES (1, 1, 'VALID_ROUTE', 1, 2, 'Route?', 'EASY', 'A',
                    'READY_FOR_REVIEW')""")
        for letter, ids, valid in [("A", [1, 2, 3, 4, 5, 6], 1),
                                   ("B", [1, 2, 3, 4, 5, 7], 0),
                                   ("C", [1, 2, 3, 4, 5, 8], 0)]:
            db.execute("""INSERT INTO question_options
                        (question_id, option_letter, display_sequence_json, is_valid, is_correct)
                        VALUES (1, ?, ?, ?, ?)""",
                       (letter, json.dumps(ids), valid, int(letter == "A")))
        assert export_approved(db, target) == 0
        review_question(db, 1, "APPROVED", "checked")
        assert export_approved(db, target) == 1
        with sqlite3.connect(target) as app:
            assert app.execute("SELECT count(*) FROM questions").fetchone()[0] == 1
            assert app.execute("SELECT route_text FROM question_options WHERE option_letter='A'").fetchone()[0].startswith("Calle 1 →")


def test_export_rejects_invalid_approved_question(tmp_path):
    source = tmp_path / "generator.sqlite"
    init_db(source)
    with connect(source) as db:
        db.execute("INSERT INTO generator_runs (id) VALUES (1)")
        db.execute("INSERT INTO hitos (id, canonical_name, source_address) VALUES (1, 'A', 'A')")
        db.execute("INSERT INTO hitos (id, canonical_name, source_address) VALUES (2, 'B', 'B')")
        db.execute("""INSERT INTO questions (generator_run_id, question_type, origin_hito_id,
                    destination_hito_id, wording, difficulty, correct_option, status)
                    VALUES (1, 'VALID_ROUTE', 1, 2, 'Route?', 'EASY', 'A', 'APPROVED')""")
        with pytest.raises(ValueError, match="failed validation"):
            export_approved(db, tmp_path / "app.sqlite")
