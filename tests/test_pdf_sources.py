from pathlib import Path

import pytest

from callejero_generator.db import connect, init_db
from callejero_generator.pdf_sources import import_pdf_sources
from callejero_generator.sample_exam import extract_exam
from callejero_generator.settings import load_source_paths

ROOT = Path(__file__).resolve().parents[1]
SOURCES = load_source_paths(ROOT / "config" / "generator.example.yaml")


@pytest.mark.skipif(not all((ROOT / path).exists() for path in SOURCES.values()),
                    reason="Source PDFs are distributed separately")
def test_real_pdf_import_and_exam_structure(tmp_path):
    database = tmp_path / "generator.sqlite"
    init_db(database)
    with connect(database) as connection:
        counts = import_pdf_sources(connection, ROOT / SOURCES["espacios_pdf"],
                                    ROOT / SOURCES["hitos_pdf"])
        assert counts == (2934, 517)
        espacio = connection.execute(
            "SELECT canonical_name, source_ref FROM espacios WHERE canonical_name='Avenida de América'"
        ).fetchone()
        assert espacio["source_ref"].startswith("EspaciosCirculatorios_")
        hito = connection.execute(
            "SELECT source_address FROM hitos WHERE canonical_name='Telefónica'"
        ).fetchone()
        assert "Rda. de la Comunicación" in hito["source_address"]
        imports = connection.execute(
            "SELECT source_type, row_count, length(sha256) FROM source_imports ORDER BY source_type"
        ).fetchall()
        assert [tuple(row) for row in imports] == [("ESPACIOS", 2934, 64), ("HITOS", 517, 64)]
    questions = extract_exam(ROOT / SOURCES["sample_exam_pdf"])
    assert len(questions) == 30
    assert all(set(question.options) == {"A", "B", "C"} for question in questions)
    assert questions[0].mentions_emergency
    assert questions[3].page == 2  # continuation spans the next PDF page
    assert len(questions[3].components["A"]) >= 10
