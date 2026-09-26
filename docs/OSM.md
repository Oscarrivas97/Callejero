# Madrid OSM graph

## Pinned extract

The graph build uses the [Geofabrik Madrid extract](https://download.geofabrik.de/europe/spain/madrid.html). This repository pins the archived `madrid-260923.osm.pbf` snapshot so a later `latest` download cannot silently change routing results. The PBF is ignored by Git.

```bash
mkdir -p data/osm
curl -fL --retry 3 -o data/osm/madrid-260923.osm.pbf \
  https://download.geofabrik.de/europe/spain/madrid-260923.osm.pbf
sha256sum data/osm/madrid-260923.osm.pbf
```

Expected SHA-256:

```text
648edee38a0f1eb1fbb4ff6478468bc3388565fff2975f258fa7a9b812752ee9
```

The URL, hash, and snapshot date are also in `config/generator.example.yaml`. Geofabrik attributes its data to OpenStreetMap contributors under ODbL; retain that attribution when distributing derived data.

The PBF replication header reports data through `2026-09-23T20:22:04Z`.

## Build and inspect

After `callejero init-db` and `callejero import-pdfs`:

```bash
.venv/bin/callejero build-osm-graph
.venv/bin/callejero validate-osm-option ORIGIN_NODE DESTINATION_NODE 10,20,30
```

The graph is written to `data/working/madrid_graph.sqlite` with its PBF hash, source URL, snapshot date, and build counts in `metadata`. Node IDs are OSM node IDs; the validation command is a diagnostic until reviewed Hito attachments are available.

A smoke check for this pinned snapshot traverses Plaza de Grecia (Espacio ID 2741) and Avenida de Niza (ID 158):

```bash
.venv/bin/callejero validate-osm-option 20952914 20952920 2741,158
```

The current build contains 850,265 nodes, 1,361,464 directed edges, 151,521 edges with canonical Espacio mappings, and 10,479 forbidden edge-to-edge turns. About 10% of the region's directed road length currently maps to Espacios, so mapping coverage needs work before question generation.

The importer streams the PBF with Pyosmium. It creates directed segments for drivable OSM ways, applies one-way rules, estimates distance from node coordinates, maps unambiguous street names to canonical Espacios, and materializes node-based `no_*` and `only_*` turn restrictions. The SQLite validator searches for a legal path whose Espacio projection matches the displayed sequence exactly.

Via-way and unsupported restriction relations are recorded. Searches that depend on turns from their affected ways or at their identified junction nodes return `INDETERMINATE` rather than a valid answer. Conditional access and complex vehicle-specific rules still need dedicated handling. The graph is therefore useful for validation development and diagnostics; it is not yet a basis for approving production questions.

See [turn-restriction follow-up](OSM_RESTRICTIONS_BACKLOG.md) for the audited categories, implementation order, and acceptance checks.
