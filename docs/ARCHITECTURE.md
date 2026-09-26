# Architecture

## 1. High-level design

```text
PDF/source import
      │
      ├── Hitos ───────────────┐
      │                        │
      └── Espacios ───────┐    │
                          │    │
OSM extract ──────────────┼────┤
                          ▼    ▼
                    normalized data
                          │
             ┌────────────┴─────────────┐
             ▼                          ▼
       Hito geocoding             OSM-Espacio mapping
             │                          │
             └────────────┬─────────────┘
                          ▼
                     road graph
                          │
                          ▼
                  candidate routing
                          │
                          ▼
                legality validation
                          │
                          ▼
                Espacios projection
                          │
                          ▼
                 question builder
                          │
                          ▼
             ambiguity / quality rules
                          │
                          ▼
                    manual review
                          │
                          ▼
                      APPROVED
                          │
                          ▼
                  app SQLite export
```

## 2. Suggested Python packages/modules

```text
src/callejero_generator/
├── cli.py
├── settings.py
├── db.py
├── importers/
│   ├── espacios.py
│   ├── hitos.py
│   └── sample_exam.py
├── normalization/
│   ├── street_names.py
│   ├── aliases.py
│   └── fuzzy.py
├── geocoding/
│   ├── provider.py
│   ├── scoring.py
│   └── snapping.py
├── osm/
│   ├── import_graph.py
│   ├── restrictions.py
│   └── mapping.py
├── routing/
│   ├── shortest.py
│   ├── alternatives.py
│   ├── cost.py
│   └── similarity.py
├── projection/
│   ├── route_to_espacios.py
│   └── hidden_segments.py
├── questions/
│   ├── normal.py
│   ├── fastest.py
│   ├── distractors.py
│   └── difficulty.py
├── validation/
│   ├── route.py
│   ├── option.py
│   ├── question.py
│   └── quality.py
├── review/
│   ├── service.py
│   └── ui.py
└── export/
    ├── sqlite.py
    └── manifest.py
```

## 3. Separation of concerns

### Import layer
Converts source material into structured rows. No routing logic.

### Normalization layer
Owns canonical string rules and aliases.

### OSM mapping layer
Links OSM graph objects to canonical Espacio IDs.

### Routing layer
Works only with the physical graph and travel costs.

### Projection layer
Converts physical routes into exam routes.

### Question layer
Creates A/B/C semantics.

### Validation layer
Determines whether candidate questions satisfy the specification.

### Review layer
Allows manual approval/correction.

### Export layer
Creates the stripped-down DB used by the mobile application.

## 4. Determinism

Given identical:

- source datasets;
- OSM snapshot;
- config;
- random seed;
- generator version;

the pipeline should produce reproducible candidates.

Store the random seed for each generation run.

## 5. Offline-first processing

After obtaining the OSM extract and geocoding required Hitos, normal question generation should run without internet access.

If a remote geocoder is initially used, persist all resolved Hitos locally.

## 6. Review UI

V1 can begin as:

- CLI + generated HTML map/report; or
- lightweight local web UI.

A local web UI is preferable once generation works because map inspection will be important.

The review UI is not part of the mobile app.
