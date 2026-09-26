# Product Specification — Callejero Question Generator V1

## 1. Product purpose

The Question Generator is a **developer-side Python product** that produces a trusted database of route questions for the Callejero app.

The mobile app consumes only pre-generated, pre-validated, manually approved questions. It does not perform routing or validation.

## 2. Source data

### 2.1 Espacios Circulatorios

The Espacios source is authoritative for answer vocabulary.

Rules:

- Anything displayed as a route component must resolve to an Espacio.
- The exact name stored from the Espacios source is the canonical display string.
- Similar strings, abbreviations, punctuation variants, accents, and commonly used forms map to that canonical string.
- An OSM road may map to one Espacio even if OSM names it differently.
- If the mapping is ambiguous, the record is flagged for manual review.

### 2.2 Hitos

The Hitos source provides:

- canonical Hito name;
- original source address.

The system derives:

- latitude;
- longitude;
- snapped OSM edge/node;
- geocoding confidence;
- manual verification status.

### 2.3 Sample exam

The sample exam is used as:

- style reference;
- naming-variant reference;
- regression suite;
- source for realistic route-option similarity;
- reference for answer-length/difficulty tuning.

It must **not** be treated as a complete truth set for all Madrid routing.

## 3. V1 scope

### Included

- Hito → Hito questions.
- Three options per question: A, B, C.
- Normal road rules.
- Legal connectivity.
- One-way restrictions.
- Turn restrictions where represented by the routing graph.
- Estimated travel time.
- Offline map data.
- Manual approval.
- SQLite export for app use.

### Deferred

- Emergency vehicle routing.
- Intersection endpoints.
- Hito ↔ intersection questions.
- Dynamic route calculation in the app.
- Live traffic.
- Temporary closures.
- Signal timing.
- Automatic publishing without review.

## 4. Question semantics

### 4.1 VALID_ROUTE

The question asks for the correct route.

Requirements:

- exactly 1 option must validate as a legal origin-to-destination route;
- exactly 2 options must be invalid;
- all displayed route elements in all three options must belong to Espacios;
- distractors must be plausible and should ideally contain one controlled defect;
- if more than one option validates, reject the entire question.

### 4.2 FASTEST_ROUTE

The question explicitly asks for the fastest route.

Requirements:

- all three options must be valid origin-to-destination routes;
- all three must be meaningfully different;
- one route must be clearly faster according to the configured estimated-time model;
- reject if the winner is within the ambiguity threshold of the runner-up.

## 5. Route model

The system maintains two separate route representations.

### 5.1 Physical route

Full OSM path containing every traversed graph edge.

Used for:

- legality;
- direction;
- turn restrictions;
- distance;
- estimated time;
- route diversity;
- debugging.

### 5.2 Exam route

Projected route containing only Espacios Circulatorios.

Used for:

- displayed answer;
- difficulty;
- distractor generation;
- app export.

Non-Espacio roads may exist physically and be omitted from the displayed route.

## 6. Physical → exam projection

For every physical OSM edge:

1. Resolve its road identity.
2. Attempt to map the edge to an Espacio.
3. If mapped, emit the canonical Espacio ID.
4. If unmapped, omit it from the displayed sequence but retain it in physical-route metadata.
5. Collapse **consecutive** duplicate Espacios.
6. Do not remove non-consecutive repetitions.

Example:

```text
Physical:
A → local X → B → B → connector Y → C → A

Exam:
A → B → C → A
```

## 7. Espacio matching

Matching precedence:

1. canonical exact match;
2. exact alias;
3. normalized exact match;
4. high-confidence fuzzy match;
5. spatially assisted name match;
6. unresolved/manual review.

Normalization should handle at least:

- case;
- accents;
- punctuation;
- repeated spaces;
- `C/`, `C.`, `Calle`;
- `Av.`, `Av`, `Avenida`;
- `Pº`, `P.º`, `Paseo`;
- `Gta.`, `Glorieta`;
- `Pl.`, `Plaza`;
- `Ctra.`, `Crt.`, `Carretera`;
- hyphen variants;
- common OCR artifacts.

Automatic fuzzy matching must never silently create a permanent low-confidence mapping.

## 8. Special variants

The Espacio canonical entry remains the truth.

Direction or carriageway variants are stored as metadata, for example:

```text
canonical Espacio: Autovía M-30
variant: INTERIOR
```

Examples of variant metadata:

- INTERIOR;
- EXTERIOR;
- LATERAL;
- CENTRAL;
- TUNNEL;
- SERVICE_ROAD;
- ACCESS;
- BRIDGE;
- ELEVATED.

A variant does not become a separate canonical Espacio unless the source itself defines it separately.

## 9. Hito geocoding and snapping

Pipeline:

1. geocode original address;
2. obtain one or more coordinate candidates;
3. score candidates;
4. snap to a drivable OSM edge appropriate for access;
5. store confidence;
6. manually review uncertain cases;
7. persist the approved graph attachment.

The generator should not geocode the same approved Hito on every run.

## 10. Geographic coverage

The OSM extract must cover:

- Madrid municipality;
- M-40;
- M-45;
- M-50;
- connecting road infrastructure needed by candidate routes.

The exact bounding polygon should be configurable.

## 11. Routing cost

Primary route cost:

```text
estimated driving time
```

Edge travel time:

```text
edge length / expected speed
```

Speed source:

1. explicit OSM `maxspeed` when usable;
2. configured default by OSM `highway` class otherwise.

Do not use live or historical traffic in V1.

## 12. Legal validation

V1 validates:

- graph connectivity;
- allowed travel direction;
- OSM turn restrictions supported by the selected routing implementation.

A route failing any legal check is invalid.

## 13. Candidate route generation

For each selected Hito pair:

1. generate K alternative legal physical routes;
2. calculate distance/time;
3. project each route to Espacios;
4. discard poor projections;
5. calculate pairwise similarity;
6. choose useful candidates for question construction.

K is configurable. Initial recommended range: 10–20.

## 14. Route diversity

Alternatives should share enough structure to look plausible but differ substantially enough to test knowledge.

Measure both:

- physical-edge overlap;
- displayed-Espacio overlap.

Initial configurable target overlap:

```text
30%–75%
```

This is a tuning range, not an immutable rule.

Reject routes that are:

- nearly identical;
- almost completely unrelated;
- obviously circuitous compared with comparable candidates.

## 15. Hidden non-Espacio travel

Because the answer-only restriction is authoritative, hidden roads are permitted.

Track:

- hidden distance;
- hidden distance ratio;
- hidden edge count;
- largest hidden gap between displayed Espacios.

Initial heuristic:

```text
hidden_distance_ratio <= 0.30
```

Questions exceeding the threshold are rejected or require explicit manual override.

## 16. Minimum answer size and difficulty

Questions with very few displayed Espacios are rejected.

Initial V1 thresholds:

```text
minimum accepted answer: 6 Espacios

EASY:   6–9
MEDIUM: 10–14
HARD:   15+
```

Primary difficulty inputs:

1. number of displayed Espacios;
2. similarity/plausibility of alternatives.

Secondary metadata:

- physical distance;
- estimated time;
- hidden-road ratio;
- route overlap.

Target generation mix:

```text
EASY   ~25%
MEDIUM ~50%
HARD   ~25%
```

All thresholds must be configuration, not hard-coded constants.

## 17. VALID_ROUTE distractors

Distractors are derived from realistic route structure rather than random Madrid streets.

Preferred failure modes:

- `DISCONNECTED_TRANSITION`;
- `WRONG_DIRECTION`;
- `PROHIBITED_TURN`.

Preferred construction:

```text
Correct:
A → B → C → D → E → F

Distractor:
A → B → C → X → E → F
```

`X` must be an Espacio.

A distractor should ideally fail for one primary reason.

## 18. Distractor validation

Every option is independently validated against the road graph.

A VALID_ROUTE question is accepted only if the final result is exactly:

```text
1 valid
2 invalid
```

Any `2 valid / 1 invalid` or `3 valid` result is rejected.

## 19. FASTEST_ROUTE construction

1. Generate multiple legal alternatives.
2. Project them to Espacios.
3. Select three sufficiently distinct routes.
4. Verify all three are valid.
5. Calculate estimated travel time.
6. Sort by cost.
7. Apply ambiguity threshold.

Initial ambiguity rule:

```text
winner advantage >= max(5%, 30 seconds)
```

Make both values configurable.

## 20. Automatic rejection

Reject a candidate question when any of the following applies:

- unresolved origin Hito;
- unresolved destination Hito;
- route disconnected;
- illegal direction;
- prohibited turn;
- fewer than configured minimum Espacios;
- excessive hidden-road ratio;
- unresolved critical Espacio mapping;
- extreme detour;
- unnecessary loop;
- duplicate question;
- poor alternative diversity;
- alternatives nearly identical;
- normal question has more than one valid option;
- fastest question contains an invalid option;
- fastest winner fails the ambiguity threshold.

## 21. Quality metrics

Store quality metadata for review:

- mapping confidence;
- Hito snap confidence;
- route time;
- route distance;
- Espacios count;
- hidden distance ratio;
- physical overlap;
- Espacio overlap;
- ambiguity margin;
- validation result;
- reason for rejection.

## 22. Manual review

Question statuses:

```text
GENERATED
AUTO_REJECTED
READY_FOR_REVIEW
APPROVED
REJECTED
```

Reviewer must be able to see:

- origin;
- destination;
- question type;
- difficulty;
- A/B/C;
- correct option;
- physical route;
- displayed route;
- map visualization;
- route times;
- route distances;
- Espacios count;
- hidden distance;
- overlap;
- validation diagnostics.

Reviewer actions:

- approve;
- reject;
- edit mapping;
- mark Hito mapping for correction;
- regenerate alternatives.

## 23. Learning from review

Manual changes should persist.

Persist:

- accepted aliases;
- OSM → Espacio mappings;
- rejected mappings;
- Hito snaps;
- problematic OSM segments;
- special variants;
- reviewer notes.

Later generator runs must reuse these decisions.

## 24. Regression strategy

The sample exam should become a permanent regression fixture.

Use it to test:

- text normalization;
- alias resolution;
- Hito resolution;
- variant handling;
- route-option structure;
- expected route complexity;
- similarity between alternatives;
- legality checks where the exam data allows reliable reconstruction.

The objective is not necessarily to reproduce an author’s route exactly. The objective is to ensure the generator behaves consistently with the source style and does not produce obviously incompatible questions.

## 25. Export contract

Only APPROVED questions are exported to the app DB.

The app DB should contain no generation-only data.

Minimum exported fields:

- question ID;
- question type;
- origin Hito;
- destination Hito;
- difficulty;
- wording;
- option A Espacio sequence;
- option B Espacio sequence;
- option C Espacio sequence;
- correct option.

Optional app metadata:

- estimated time;
- distance;
- tags;
- source generation version.

## 26. Versioning

Every generator run and exported DB must record:

- generator version;
- schema version;
- Hitos source version;
- Espacios source version;
- OSM snapshot date/version;
- configuration hash;
- validation-rule version.

Approved questions must remain reproducible.
