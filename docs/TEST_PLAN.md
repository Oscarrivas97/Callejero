# Test Plan

## 1. Unit tests

### Name normalization

Test equivalent forms such as:

```text
Av. de América
Av de America
Avenida de América
```

Expected: same canonical Espacio.

Test false friends to ensure fuzzy matching does not merge unrelated names.

### Consecutive duplicate collapse

Input:

```text
A A A B B C A
```

Expected:

```text
A B C A
```

### Hidden ratio

Verify calculation and configured threshold behavior.

### Speed defaults

- explicit maxspeed;
- missing maxspeed;
- malformed maxspeed;
- highway-class fallback.

### Difficulty

Boundary tests around every configured Espacios-count threshold.

## 2. Integration tests

### Hito geocoding + snapping

For a reviewed Hito, repeated runs should resolve to the persisted approved graph attachment.

### OSM → Espacio mapping

Test:

- canonical exact;
- alias;
- normalized match;
- fuzzy candidate;
- unresolved result.

### Route legality

Fixture cases for:

- legal one-way;
- illegal reverse direction;
- allowed turn;
- restricted turn.

### Projection

Physical route with mapped and unmapped roads should yield the expected displayed sequence.

## 3. Question validation tests

### VALID_ROUTE

Accept:

```text
A valid
B invalid
C invalid
```

Reject:

```text
A valid
B valid
C invalid
```

Reject:

```text
A invalid
B invalid
C invalid
```

### FASTEST_ROUTE

Accept only when:

```text
all valid
winner exceeds configured margin
```

## 4. Regression tests from sample exam

Create fixtures for representative questions covering:

- Hito → Hito;
- long routes;
- short routes;
- repeated road names;
- motorway variants;
- tunnels/accesses;
- options sharing large route portions;
- options that diverge mid-route.

The regression goal is structural compatibility and robust normalization, not necessarily identical shortest-path output.

## 5. Data quality tests

Before generation:

```text
100% Espacios have a canonical normalized form
no duplicate canonical Espacio IDs
all approved aliases resolve to exactly one Espacio
all APPROVED Hitos have coordinates and graph attachment
```

Before export:

```text
question.status == APPROVED
exactly 3 options
correct option in {A,B,C}
all displayed elements resolve to Espacios
VALID_ROUTE has exactly one valid option
FASTEST_ROUTE has exactly three valid options
no duplicate question signature
```

## 6. Property tests

Useful properties:

- exported route strings never contain a non-Espacio canonical ID;
- randomizing option order never changes semantic correctness;
- re-running validation on an approved question gives the same result for the same OSM/config versions;
- projection never reorders mapped Espacios.

## 7. Manual review metrics

Track:

```text
approval rate
rejection reason distribution
average Espacios count
hidden ratio distribution
difficulty distribution
route-overlap distribution
manual alias corrections
manual Hito corrections
```

High manual rejection for one category should trigger algorithm/config changes.
