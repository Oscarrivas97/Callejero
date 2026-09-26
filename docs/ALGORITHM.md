# Generation Algorithm

## 1. Preprocessing

### A. Import Espacios

For each source entry:

```python
Espacio(
    canonical_name=source_name,
    normalized_name=normalize(source_name),
    status="ACTIVE",
)
```

Generate baseline aliases automatically, but distinguish:

- generated aliases;
- manually approved aliases.

### B. Import Hitos

Store source Hito name and address exactly.

### C. Build/import OSM graph

Graph edges need at least:

```text
edge_id
from_node
to_node
length_m
highway_class
maxspeed
name
oneway
geometry
restriction metadata
```

### D. Resolve Hitos

For each Hito:

```text
geocode
→ score candidate
→ snap to drivable graph
→ persist
```

### E. Map OSM roads to Espacios

Use:

```text
name normalization
+ aliases
+ geometry/location
+ manual mapping overrides
```

---

## 2. Selecting candidate Hito pairs

Pseudo-code:

```python
for origin, destination in sampled_hito_pairs:
    if origin == destination:
        continue

    straight_line = distance(origin, destination)

    if outside_generation_bounds(straight_line):
        continue

    generate_question(origin, destination)
```

Pair sampling should support target buckets:

```text
short
medium
long
```

Distance bucket boundaries should be derived from generated route distribution and then frozen in config.

---

## 3. Generate K physical routes

```python
routes = k_alternative_routes(
    origin.snap,
    destination.snap,
    k=config.routing.candidate_count,
    weight="estimated_time",
)
```

For every route calculate:

```text
total distance
estimated time
edge list
road list
loop score
```

Remove exact/near duplicates.

---

## 4. Validate physical routes

```python
for route in routes:
    assert connected(route)
    assert legal_direction(route)
    assert turn_restrictions_satisfied(route)
```

Invalid physical routes are discarded before projection.

---

## 5. Project route to Espacios

```python
def project(route):
    result = []
    hidden_distance = 0

    for edge in route.edges:
        mapping = resolve_espacio(edge)

        if mapping:
            if not result or result[-1].espacio_id != mapping.espacio_id:
                result.append(mapping)
        else:
            hidden_distance += edge.length

    return ProjectedRoute(
        espacios=result,
        hidden_distance=hidden_distance,
        hidden_ratio=hidden_distance / route.total_distance,
    )
```

Preserve variant metadata per emitted item.

---

## 6. Reject weak projections

Reject when:

```text
Espacios count < minimum
hidden ratio > threshold
critical mapping unresolved
projection is empty
projection is dominated by one repeated Espacio
```

---

## 7. Compute diversity

For route pairs calculate:

```text
physical_overlap
espacio_overlap
time_ratio
distance_ratio
```

Keep alternatives that fall within configured similarity targets.

---

## 8. VALID_ROUTE generation

### Correct option

Choose a high-quality legal route with:

```text
good mapping confidence
reasonable hidden ratio
appropriate difficulty
no pathological detour
```

### Distractor 1

Attempt one controlled mutation:

```text
select transition i → j
find nearby Espacio X
replace/insert X
require resulting displayed sequence to fail validation
```

### Distractor 2

Use a different failure category if possible.

Priority:

```text
DISCONNECTED_TRANSITION
WRONG_DIRECTION
PROHIBITED_TURN
```

### Final check

```python
results = [validate_option(o) for o in options]

if sum(r.is_valid for r in results) != 1:
    reject()
```

Randomize A/B/C only after validation.

---

## 9. FASTEST_ROUTE generation

Select three legal, sufficiently diverse projected routes.

```python
assert all(validate_option(o).is_valid for o in options)

ranked = sorted(options, key=lambda x: x.estimated_time)
winner = ranked[0]
runner_up = ranked[1]

delta_seconds = runner_up.time - winner.time
delta_ratio = delta_seconds / winner.time

if delta_seconds < config.fastest.min_seconds:
    reject()

if delta_ratio < config.fastest.min_ratio:
    reject()
```

Recommended V1 logic:

```text
require BOTH:
>= 30 seconds
>= 5%
```

If later testing shows this is too strict, make the combination policy configurable.

---

## 10. Option validator

A displayed option is a sequence of Espacios.

The validator must determine whether there exists a legal physical path that:

1. begins at the origin Hito attachment;
2. visits the displayed Espacios in the displayed order;
3. ends at the destination Hito attachment;
4. respects normal traffic legality.

This is not the same as checking whether adjacent names intersect geometrically.

Validation should operate as a constrained path problem.

Conceptually:

```text
origin
  ↓
must encounter Espacio A
  ↓
must encounter Espacio B
  ↓
must encounter Espacio C
  ↓
destination
```

Hidden non-Espacio edges are allowed between displayed Espacios.

For distractors, the sequence should fail this constrained validation.

---

## 11. Prevent accidental ambiguity

After constructing A/B/C:

### VALID_ROUTE

```text
valid_count == 1
```

### FASTEST_ROUTE

```text
valid_count == 3
clear_time_winner == true
```

Otherwise reject.

---

## 12. Deduplication

Compute a normalized signature such as:

```text
question_type
origin_hito
destination_hito
sorted option route hashes
```

Also check reverse-pair policy separately.

Two questions with the same origin/destination may coexist only if the route alternatives differ substantially and the product intentionally allows it.

---

## 13. Persist full provenance

For every generated candidate store:

```text
generator_run_id
random_seed
origin
destination
physical routes
projected routes
validation results
quality metrics
rejection reason
config hash
OSM version
```

Never rely solely on the exported app representation for debugging.
