PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS espacios (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    source_ref TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS espacio_aliases (
    id INTEGER PRIMARY KEY,
    espacio_id INTEGER NOT NULL REFERENCES espacios(id),
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    source TEXT,
    confidence REAL,
    manually_approved INTEGER NOT NULL DEFAULT 0,
    UNIQUE (espacio_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS hitos (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    source_address TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    geocode_confidence REAL,
    osm_edge_id TEXT,
    snap_offset_m REAL,
    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
    source_ref TEXT
);

CREATE TABLE IF NOT EXISTS osm_espacio_mapping (
    id INTEGER PRIMARY KEY,
    osm_object_type TEXT NOT NULL,
    osm_object_id TEXT NOT NULL,
    osm_name TEXT,
    espacio_id INTEGER NOT NULL REFERENCES espacios(id),
    variant TEXT,
    confidence REAL,
    mapping_method TEXT,
    manually_approved INTEGER NOT NULL DEFAULT 0,
    UNIQUE (osm_object_type, osm_object_id, espacio_id, variant)
);

CREATE TABLE IF NOT EXISTS generator_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT,
    finished_at TEXT,
    random_seed INTEGER,
    generator_version TEXT,
    osm_version TEXT,
    config_hash TEXT,
    source_versions_json TEXT
);

CREATE TABLE IF NOT EXISTS physical_routes (
    id INTEGER PRIMARY KEY,
    generator_run_id INTEGER NOT NULL REFERENCES generator_runs(id),
    origin_hito_id INTEGER NOT NULL REFERENCES hitos(id),
    destination_hito_id INTEGER NOT NULL REFERENCES hitos(id),
    distance_m REAL NOT NULL,
    estimated_time_s REAL NOT NULL,
    edge_sequence_json TEXT NOT NULL,
    geometry_json TEXT,
    legal INTEGER NOT NULL,
    validation_json TEXT
);

CREATE TABLE IF NOT EXISTS projected_routes (
    id INTEGER PRIMARY KEY,
    physical_route_id INTEGER NOT NULL REFERENCES physical_routes(id),
    espacio_sequence_json TEXT NOT NULL,
    variant_sequence_json TEXT,
    espacios_count INTEGER NOT NULL,
    hidden_distance_m REAL NOT NULL DEFAULT 0,
    hidden_ratio REAL NOT NULL DEFAULT 0,
    mapping_confidence REAL,
    projection_json TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    generator_run_id INTEGER NOT NULL REFERENCES generator_runs(id),
    question_type TEXT NOT NULL CHECK (question_type IN ('VALID_ROUTE','FASTEST_ROUTE')),
    origin_hito_id INTEGER NOT NULL REFERENCES hitos(id),
    destination_hito_id INTEGER NOT NULL REFERENCES hitos(id),
    wording TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('EASY','MEDIUM','HARD')),
    correct_option TEXT CHECK (correct_option IN ('A','B','C')),
    status TEXT NOT NULL CHECK (status IN ('GENERATED','AUTO_REJECTED','READY_FOR_REVIEW','APPROVED','REJECTED')),
    quality_score REAL,
    rejection_reason TEXT,
    created_at TEXT,
    reviewed_at TEXT,
    reviewer_note TEXT
);

CREATE TABLE IF NOT EXISTS question_options (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_letter TEXT NOT NULL CHECK (option_letter IN ('A','B','C')),
    projected_route_id INTEGER REFERENCES projected_routes(id),
    display_sequence_json TEXT NOT NULL,
    is_valid INTEGER NOT NULL,
    is_correct INTEGER NOT NULL,
    failure_reason TEXT,
    estimated_time_s REAL,
    distance_m REAL,
    validation_json TEXT,
    UNIQUE (question_id, option_letter)
);

CREATE TABLE IF NOT EXISTS review_history (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alias_norm ON espacio_aliases(normalized_alias);
CREATE INDEX IF NOT EXISTS idx_hitos_review ON hitos(review_status);
CREATE INDEX IF NOT EXISTS idx_question_status ON questions(status);
CREATE INDEX IF NOT EXISTS idx_question_pair ON questions(origin_hito_id, destination_hito_id);
