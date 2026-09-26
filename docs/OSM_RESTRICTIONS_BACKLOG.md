# OSM turn-restriction follow-up

This records the restriction work needed before the Madrid graph can validate production questions. The baseline is the pinned `madrid-260923.osm.pbf` snapshot documented in [OSM.md](OSM.md), built with graph code at commit `4590107`.

## Baseline

The current graph materializes 10,479 forbidden edge-to-edge turns and records 85 relations it cannot fully interpret:

| Reason in graph DB | Count | Observed shape |
| --- | ---: | --- |
| `VIA_WAY` | 53 | `from` way, one or more `via` ways, `to` way |
| `UNSUPPORTED_MEMBERS` | 29 | Missing `from`, `to`, or `via` members; 22 contain only a `via` node |
| `CONDITIONAL` | 2 | Weight-dependent `restriction:conditional` without an unconditional rule |
| `UNKNOWN_RESTRICTION` | 1 | Heavy-vehicle conditional tag without a general restriction |

All 22 `via`-only junction nodes are present in the driving graph. Commit `4590107` made turns at identified junctions, and turns from identified affected ways, return `INDETERMINATE`. Keep that behavior until each relation is understood; never convert an unknown turn into a valid one by default.

Inspect the current counts with:

```bash
.venv/bin/python - <<'PY'
import sqlite3
with sqlite3.connect('data/working/madrid_graph.sqlite') as db:
    for row in db.execute('SELECT reason, COUNT(*) FROM unsupported_restrictions GROUP BY reason ORDER BY reason'):
        print(*row)
PY
```

## Work items

### 1. Support via-way restrictions

**Priority: highest.** A via-way restriction describes a route through one or more ways. A forbidden pair of adjacent edges cannot represent the whole rule. Preserve the ordered relation members, determine legal directed entry and exit edges, and extend the routing search state with progress through active restrictions.

- For `no_*`, prohibit completion of the specified `from → via way(s) → to` path.
- For `only_*`, prohibit an exit that deviates from the specified path after entering it from the `from` way.
- Respect one-way direction and node connectivity while assembling the path. Reject ambiguous or disconnected relation geometry into the unsupported table.
- Add synthetic tests for one and multiple via ways, U-turns, legal alternate exits, and overlapping restrictions. Add pinned-snapshot regression cases such as relations `120277`, `969906`, and `4150138`.
- Compare constrained-path results before and after the change. No formerly `INDETERMINATE` path should become `VALID` without a fully modeled legal route.

**Done when:** every connected, unconditional via-way relation in the pinned snapshot is represented in the validator, and remaining via-way records have explicit diagnostic reasons.

### 2. Audit incomplete member lists

**Priority: high.** Examine the 29 `UNSUPPORTED_MEMBERS` relations against the full upstream relation and the pinned extract. Determine whether an extract boundary omitted members or the source relation itself is malformed. The 22 via-only relations need special attention because their junctions are in the driving graph.

- Produce an audit report with relation ID, raw tags and members, local graph coverage, and an upstream comparison.
- If the extract is incomplete, obtain a reference-complete relation and its member ways, then rebuild from a documented input.
- If OSM itself is malformed, record a reviewed local correction or propose an upstream OSM edit with evidence. Do not infer missing `from`/`to` ways from proximity alone.
- Keep junction-level `INDETERMINATE` behavior for unresolved entries.

**Done when:** every one of the 29 entries is classified as extract incompleteness, source-data defect, or irrelevant to the configured vehicle, with a reproducible decision recorded.

### 3. Define the vehicle and time profile

**Priority: high before production export.** The current V1 description says normal traffic rules but does not define vehicle weight or a departure time. That choice determines conditional access and turn restrictions. In this snapshot, relation `19820906` applies above 3.5 tonnes, relation `20682264` applies below 3.5 tonnes, and relation `19826232` is heavy-vehicle conditional.

- Specify vehicle class, permitted access, maximum weight, and whether generation assumes a particular time or rejects time-dependent routes.
- Evaluate applicable `restriction:conditional` rules against that profile; keep unresolved conditions `INDETERMINATE`.
- Revisit the importer’s current conservative exclusion of conditional-access ways and destination-only access.
- Record the profile and rule version with every generated question and exported DB.

**Done when:** each conditional relation has a tested, profile-specific outcome and a different vehicle profile cannot silently reuse the same validation result.

### 4. Strengthen diagnostics and release gate

- Store complete restriction tags and ordered members in the graph database so audits do not need another PBF scan.
- Report counts by reason and coverage at build time. Include relation IDs in route-validation diagnostics when uncertainty affects a candidate.
- Add regression tests against the pinned PBF for representative `no_*`, `only_*`, via-way, malformed, and conditional cases.
- Reject question approval/export when any option is `INDETERMINATE` or its validation profile differs from the graph/profile used for generation.

**Done when:** all accepted questions have a legal result under the exact pinned OSM snapshot and vehicle profile, and unresolved relations cannot yield an accepted answer.

## References

- [OSM turn-restriction relation format](https://wiki.openstreetmap.org/wiki/Turn_Restriction)
- [OSM conditional restrictions](https://wiki.openstreetmap.org/wiki/Conditional_restrictions)
- [Osmium extract completeness strategies](https://docs.osmcode.org/osmium/latest/osmium-extract.html)
