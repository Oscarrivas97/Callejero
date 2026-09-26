"""Command-line entry point for the first ingestion and review workflow."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

from .db import connect, init_db
from .importers import import_espacios, import_hitos
from .pdf_sources import import_pdf_sources
from .resolution import approve_alias, resolve
from .review import export_approved, review_question
from .sample_exam import write_exam_fixture
from .settings import load_quality_settings, load_source_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="callejero")
    parser.add_argument("--db", default="data/working/generator.sqlite",
                        help="Generator SQLite database")
    parser.add_argument("--config", default="config/generator.example.yaml",
                        help="Generation settings YAML")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Create the generator schema")
    for kind in ("espacios", "hitos"):
        command = commands.add_parser(f"import-{kind}", help=f"Import reviewed {kind} CSV")
        command.add_argument("csv")
    pdf_import = commands.add_parser("import-pdfs", help="Import the supplied authoritative PDFs")
    pdf_import.add_argument("--espacios")
    pdf_import.add_argument("--hitos")
    exam = commands.add_parser("extract-exam", help="Write unscored sample-exam JSON")
    exam.add_argument("--pdf")
    exam.add_argument("--output", default="data/working/sample_exam.json")
    lookup = commands.add_parser("resolve", help="Resolve an OSM street name")
    lookup.add_argument("name")
    alias = commands.add_parser("approve-alias", help="Save a reviewed Espacio alias")
    alias.add_argument("espacio_id", type=int)
    alias.add_argument("alias")
    review = commands.add_parser("review", help="Approve or reject a ready question")
    review.add_argument("question_id", type=int)
    review.add_argument("action", choices=["APPROVED", "REJECTED"])
    review.add_argument("--note", default="")
    export = commands.add_parser("export", help="Export approved questions to app SQLite")
    export.add_argument("path", nargs="?", default="data/exports/callejero_questions.sqlite")
    args = parser.parse_args(argv)

    if args.command == "init-db":
        init_db(args.db)
        print(f"Initialized {args.db}")
        return 0
    if args.command == "extract-exam":
        path = args.pdf or load_source_paths(args.config)["sample_exam_pdf"]
        print(f"Extracted {write_exam_fixture(path, args.output)} questions to {args.output}")
        return 0
    with connect(args.db) as database:
        if args.command == "import-espacios":
            print(f"Imported {import_espacios(database, args.csv)} Espacios")
        elif args.command == "import-hitos":
            print(f"Imported {import_hitos(database, args.csv)} Hitos")
        elif args.command == "import-pdfs":
            sources = load_source_paths(args.config)
            counts = import_pdf_sources(database, args.espacios or sources["espacios_pdf"],
                                        args.hitos or sources["hitos_pdf"])
            print(f"Imported {counts[0]} Espacios and {counts[1]} Hitos")
        elif args.command == "resolve":
            print(json.dumps(resolve(database, args.name).__dict__, ensure_ascii=False))
        elif args.command == "approve-alias":
            approve_alias(database, args.espacio_id, args.alias)
            print("Alias approved")
        elif args.command == "review":
            review_question(database, args.question_id, args.action, args.note)
            print(f"Question {args.question_id}: {args.action}")
        elif args.command == "export":
            settings = load_quality_settings(args.config)
            config_hash = sha256(Path(args.config).read_bytes()).hexdigest()
            print(f"Exported {export_approved(database, args.path, settings, config_hash)} approved questions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
