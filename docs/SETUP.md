# Reproducing the development setup

The three source PDFs are available locally in `assets/` and are ignored by Git. A fresh clone needs those same files placed at the paths in `config/generator.example.yaml`. The Madrid OSM extract can be downloaded using [the pinned graph instructions](OSM.md). Do not commit source data or generated databases.

## Python environment

Use Python 3.11 or newer. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests
```

This uses the dependencies declared in `pyproject.toml`. The environment is local to `.venv` and ignored by Git.

## Import the authoritative PDFs

The PDF importer reads the actual Hitos and Espacios tables, checks row shape and duplicate names, and saves page/row references plus SHA-256 source fingerprints. Run:

```bash
.venv/bin/callejero init-db
.venv/bin/callejero import-pdfs
.venv/bin/callejero resolve 'Av de America'
.venv/bin/callejero extract-exam
```

The current PDFs yield 2,934 Espacios, 517 Hitos, and 30 unscored sample-exam questions. The exam JSON is written to `data/working/sample_exam.json`; it retains prompt and option text plus heuristic component splits. The exam contains emergency-driving and intersection questions outside V1 scope, and has no answer key in the supplied PDF. It is a style and regression source only.

Build the offline road graph after import:

```bash
.venv/bin/callejero build-osm-graph
```

You can override source paths with `--espacios` and `--hitos` on `import-pdfs`, or `--pdf` on `extract-exam`. The default paths come from the YAML config. Repeated PDF imports update source strings while retaining reviewed Hito coordinates and status.

## Optional reviewed CSV staging

If a PDF row needs manual correction, you can still import a UTF-8 CSV transcription:

`data/working/espacios.csv`:

```csv
canonical_name,source_ref
Av. de América,page 1
```

`data/working/hitos.csv`:

```csv
canonical_name,source_address,source_ref
Example Hito,Av. de América 1,page 1
```

Preserve the PDF spelling in `canonical_name`. `source_ref` is optional; the other shown columns are required. The CSV importer preserves existing reviewed Hito coordinates and status when reimporting.

## Initialize and import

```bash
.venv/bin/callejero import-espacios data/working/espacios.csv
.venv/bin/callejero import-hitos data/working/hitos.csv
```

The default working database is `data/working/generator.sqlite`. Use `--db PATH` before the command to choose another database. Repeated imports update source strings while retaining reviewed coordinates and aliases. Ambiguous normalized names are reported as ambiguous; fuzzy results are suggestions for review, not approved mappings. Save a reviewed alias with:

```bash
.venv/bin/callejero approve-alias ESPACIO_ID 'Reviewed alias'
```

## Review and export

When a later generation stage has created a question with status `READY_FOR_REVIEW`, use:

```bash
.venv/bin/callejero review QUESTION_ID APPROVED --note 'Checked against map'
.venv/bin/callejero export
```

The export creates `data/exports/callejero_questions.sqlite` from approved questions only. It checks option count, canonical Espacio IDs, correct answer, and route mode rules before replacing the app database. It reads quality thresholds from the YAML config and writes a config hash and generator-run provenance into `export_metadata`. The constrained-path validator is implemented for directed graph data and tested on fixtures; no Madrid OSM graph or generated questions exist yet.

## Next implementation stages

1. Inspect the actual PDF layouts and add source-specific extractors with page references and review reports.
2. Import an offline Madrid OSM extract into the directed graph, including one-way and turn restrictions.
3. Geocode Hitos, review candidate snaps, and persist approved attachments.
4. Map OSM edges to Espacios, requiring review for ambiguous names.
5. Connect graph-backed option validation to route alternatives, question generation, and map-based review.

Do not approve questions until option validity has been computed from the Madrid graph and its results have been reviewed.
