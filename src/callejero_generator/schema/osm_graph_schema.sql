PRAGMA foreign_keys = OFF;

CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE nodes (
    node_id INTEGER PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);

CREATE TABLE edges (
    edge_id TEXT PRIMARY KEY,
    way_id INTEGER NOT NULL,
    from_node INTEGER NOT NULL,
    to_node INTEGER NOT NULL,
    length_m REAL NOT NULL,
    highway TEXT NOT NULL,
    maxspeed TEXT,
    osm_name TEXT,
    osm_ref TEXT,
    espacio_id INTEGER
);

CREATE TABLE forbidden_turns (
    incoming_edge_id TEXT NOT NULL,
    outgoing_edge_id TEXT NOT NULL,
    relation_id INTEGER NOT NULL,
    PRIMARY KEY (incoming_edge_id, outgoing_edge_id, relation_id)
);

CREATE TABLE unsupported_restrictions (
    relation_id INTEGER PRIMARY KEY,
    restriction TEXT,
    reason TEXT NOT NULL,
    affected_way_ids_json TEXT NOT NULL
);
