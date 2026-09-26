# Callejero Question Generator

Developer-side pipeline for generating, validating, reviewing, and exporting route questions for the Callejero mobile app.

## Goal

Build a Python tool that:

1. Imports the **Hitos** source (named places + addresses).
2. Imports the **Espacios Circulatorios** source (authoritative answer vocabulary).
3. Builds an offline road graph from OpenStreetMap data for Madrid and surrounding roads.
4. Geocodes and snaps Hitos to the road graph.
5. Generates candidate routes between Hitos.
6. Projects physical routes into **Espacios-only** answer sequences.
7. Generates three-option questions.
8. Validates each question automatically.
9. Sends accepted candidates to manual review.
10. Exports only approved questions to a compact SQLite database consumed by the mobile app.

The mobile app does **not** calculate routes and does **not** need OpenStreetMap data.

## Source-of-truth hierarchy

1. **Espacios Circulatorios PDF**
   - Authoritative vocabulary for anything displayed in an answer.
   - The exact PDF string is the canonical display name.
   - Variants and abbreviations map back to this canonical string.

2. **Hitos PDF**
   - Authoritative Hito names and source addresses.
   - Coordinates are derived by geocoding and reviewed when confidence is low.

3. **OpenStreetMap**
   - Used for physical road geometry, legal connectivity, one-way restrictions, turn restrictions, and estimated driving time.
   - OSM is not authoritative for the displayed Espacio name.

4. **Sample exam**
   - Used as a reference and regression suite for question style, answer structure, naming variants, route realism, and difficulty distribution.

## V1 scope

- Hito → Hito questions only.
- Three options: A, B, C.
- Normal traffic rules only.
- Offline OSM graph.
- Route cost = estimated driving time using speed limits/default highway speeds.
- No live/historical traffic.
- Manual approval required before app export.

## Question modes

### VALID_ROUTE
Exactly one option is a valid route from origin to destination.

- 1 valid option.
- 2 plausible invalid distractors.
- Reject the question if more than one option validates successfully.

### FASTEST_ROUTE
All three options are valid routes, but one must be clearly faster.

- 3 valid options.
- Winner must exceed the ambiguity threshold defined in configuration.
- Reject if the top two are too close.

## Repository layout proposed

```text
callejero-generator/
├── README.md
├── pyproject.toml
├── config/
│   └── generator.example.yaml
├── data/
│   ├── source/
│   ├── osm/
│   ├── working/
│   └── exports/
├── docs/
│   ├── PRODUCT_SPEC.md
│   ├── ARCHITECTURE.md
│   ├── ALGORITHM.md
│   ├── DATA_MODEL.md
│   └── TEST_PLAN.md
├── sql/
│   ├── generator_schema.sql
│   └── app_export_schema.sql
├── src/
│   └── callejero_generator/
│       ├── importers/
│       ├── normalization/
│       ├── geocoding/
│       ├── osm/
│       ├── routing/
│       ├── projection/
│       ├── questions/
│       ├── validation/
│       ├── review/
│       └── export/
└── tests/
    ├── unit/
    ├── integration/
    └── regression/
```

## Recommended implementation order

1. Import and normalize Espacios.
2. Import Hitos.
3. Build canonical-name + alias model.
4. Download/import Madrid OSM extract.
5. Map Espacios to OSM roads.
6. Geocode and snap Hitos.
7. Implement legal route calculation.
8. Implement physical-route → Espacios projection.
9. Reproduce/inspect sample exam cases.
10. Generate alternative routes.
11. Generate VALID_ROUTE distractors.
12. Generate FASTEST_ROUTE questions.
13. Add automatic quality filters.
14. Build manual-review workflow.
15. Export approved SQLite DB for the mobile app.

See `docs/PRODUCT_SPEC.md` for the complete requirements.

## Current implementation

The Python tool now includes direct extraction of the supplied Espacios and Hitos PDF tables, a 30-question unscored exam fixture, SQLite setup, optional reviewed CSV imports, conservative Espacio name resolution, physical-to-exam route projection, a directed-graph constrained-path validator, question-level rule checks, manual review transitions, and approved-only app export. OSM extraction, Hito geocoding, candidate generation, and map review are next stages. See [setup instructions](docs/SETUP.md) for reproducible installation and CLI usage.
