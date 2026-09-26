"""Canonical Espacio lookup with explicit ambiguity handling."""

import sqlite3
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .normalization import normalize_name


@dataclass(frozen=True)
class Resolution:
    espacio_id: int | None
    canonical_name: str | None
    method: str
    confidence: float


def resolve(connection: sqlite3.Connection, name: str, *, fuzzy_threshold: float = 90) -> Resolution:
    exact = connection.execute(
        "SELECT id, canonical_name FROM espacios WHERE active=1 AND canonical_name=?", (name,)
    ).fetchall()
    if len(exact) == 1:
        return Resolution(exact[0]["id"], exact[0]["canonical_name"], "canonical_exact", 1)

    alias = connection.execute(
        """SELECT e.id, e.canonical_name FROM espacio_aliases a
           JOIN espacios e ON e.id=a.espacio_id
           WHERE e.active=1 AND a.alias=? AND a.manually_approved=1""", (name,)
    ).fetchall()
    if len({row["id"] for row in alias}) == 1:
        return Resolution(alias[0]["id"], alias[0]["canonical_name"], "alias_exact", 1)

    normalized = normalize_name(name)
    matches = connection.execute(
        """SELECT id, canonical_name FROM espacios
           WHERE active=1 AND normalized_name=?
           UNION SELECT e.id, e.canonical_name FROM espacio_aliases a
           JOIN espacios e ON e.id=a.espacio_id
           WHERE e.active=1 AND a.normalized_alias=? AND a.manually_approved=1""",
        (normalized, normalized),
    ).fetchall()
    if len({row["id"] for row in matches}) == 1:
        return Resolution(matches[0]["id"], matches[0]["canonical_name"], "normalized", 1)
    if matches:
        return Resolution(None, None, "ambiguous", 0)

    candidates = connection.execute(
        "SELECT id, canonical_name, normalized_name FROM espacios WHERE active=1"
    ).fetchall()
    hit = process.extractOne(normalized, {r["id"]: r["normalized_name"] for r in candidates},
                             scorer=fuzz.WRatio)
    if hit and hit[1] >= fuzzy_threshold:
        candidate = next(r for r in candidates if r["id"] == hit[2])
        return Resolution(candidate["id"], candidate["canonical_name"], "fuzzy_review", hit[1] / 100)
    return Resolution(None, None, "unresolved", 0)


def approve_alias(connection: sqlite3.Connection, espacio_id: int, alias: str) -> None:
    normalized = normalize_name(alias)
    canonical_collision = connection.execute(
        "SELECT id FROM espacios WHERE active=1 AND normalized_name=? AND id<>?",
        (normalized, espacio_id),
    ).fetchone()
    if canonical_collision:
        raise ValueError("Alias conflicts with another canonical Espacio")
    collision = connection.execute(
        """SELECT espacio_id FROM espacio_aliases
           WHERE normalized_alias=? AND manually_approved=1 AND espacio_id<>?""",
        (normalized, espacio_id),
    ).fetchone()
    if collision:
        raise ValueError("Alias already resolves to another Espacio")
    connection.execute(
        """INSERT INTO espacio_aliases
           (espacio_id, alias, normalized_alias, source, confidence, manually_approved)
           VALUES (?, ?, ?, 'manual', 1, 1)
           ON CONFLICT(espacio_id, normalized_alias) DO UPDATE SET
           alias=excluded.alias, manually_approved=1""",
        (espacio_id, alias, normalized),
    )
