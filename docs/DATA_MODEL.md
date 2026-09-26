# Data Model

## Generator DB

### `espacios`

```text
id                  INTEGER PK
canonical_name      TEXT UNIQUE NOT NULL
normalized_name     TEXT NOT NULL
active              BOOLEAN NOT NULL
source_ref          TEXT
created_at          DATETIME
updated_at          DATETIME
```

### `espacio_aliases`

```text
id                  INTEGER PK
espacio_id          INTEGER FK
alias               TEXT NOT NULL
normalized_alias    TEXT NOT NULL
source              TEXT
confidence          REAL
manually_approved   BOOLEAN
UNIQUE(espacio_id, normalized_alias)
```

### `hitos`

```text
id                  INTEGER PK
canonical_name      TEXT UNIQUE NOT NULL
source_address      TEXT NOT NULL
latitude            REAL
longitude           REAL
geocode_confidence  REAL
osm_edge_id         TEXT
snap_offset_m       REAL
review_status       TEXT
source_ref          TEXT
```

### `osm_espacio_mapping`

```text
id                  INTEGER PK
osm_object_type     TEXT
osm_object_id       TEXT
osm_name            TEXT
espacio_id          INTEGER FK
variant             TEXT
confidence          REAL
mapping_method      TEXT
manually_approved   BOOLEAN
UNIQUE(osm_object_type, osm_object_id, espacio_id, variant)
```

### `generator_runs`

```text
id                  INTEGER PK
started_at          DATETIME
finished_at         DATETIME
random_seed         INTEGER
generator_version   TEXT
osm_version         TEXT
config_hash         TEXT
source_versions_json TEXT
```

### `physical_routes`

```text
id                  INTEGER PK
generator_run_id    INTEGER FK
origin_hito_id      INTEGER FK
destination_hito_id INTEGER FK
distance_m          REAL
estimated_time_s    REAL
edge_sequence_json  TEXT
geometry_json       TEXT
legal               BOOLEAN
validation_json     TEXT
```

### `projected_routes`

```text
id                  INTEGER PK
physical_route_id   INTEGER FK
espacio_sequence_json TEXT
variant_sequence_json TEXT
espacios_count      INTEGER
hidden_distance_m   REAL
hidden_ratio        REAL
mapping_confidence  REAL
projection_json     TEXT
```

### `questions`

```text
id                  INTEGER PK
generator_run_id    INTEGER FK
question_type       TEXT
origin_hito_id      INTEGER FK
destination_hito_id INTEGER FK
wording             TEXT
difficulty          TEXT
correct_option      TEXT
status              TEXT
quality_score       REAL
rejection_reason    TEXT
created_at          DATETIME
reviewed_at         DATETIME
reviewer_note       TEXT
```

### `question_options`

```text
id                  INTEGER PK
question_id         INTEGER FK
option_letter       TEXT
projected_route_id  INTEGER FK NULL
display_sequence_json TEXT
is_valid            BOOLEAN
is_correct          BOOLEAN
failure_reason      TEXT
estimated_time_s    REAL
distance_m          REAL
validation_json     TEXT
```

### `review_history`

```text
id                  INTEGER PK
question_id         INTEGER FK
action              TEXT
note                TEXT
created_at          DATETIME
```

---

## App export DB

Only approved, presentation-ready content.

### `hitos`

```text
id
name
```

### `questions`

```text
id
type
origin_hito_id
destination_hito_id
wording
difficulty
correct_option
```

### `question_options`

```text
question_id
option_letter
route_text
route_json
```

No OSM graph, geocoding data, review diagnostics, or generator internals are included.
