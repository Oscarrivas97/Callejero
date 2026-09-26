"""Import reviewed tabular transcriptions of the authoritative PDFs."""

import csv
import sqlite3
from pathlib import Path

from .normalization import normalize_name


def _rows(path: str | Path, required: set[str]) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path} needs columns: {', '.join(sorted(required))}")
        rows = list(reader)
    if any(not all((row.get(key) or "").strip() for key in required) for row in rows):
        raise ValueError(f"{path} contains blank required fields")
    return rows


def import_espacios(connection: sqlite3.Connection, path: str | Path) -> int:
    rows = _rows(path, {"canonical_name"})
    for row in rows:
        name = row["canonical_name"].strip()
        connection.execute(
            """INSERT INTO espacios (canonical_name, normalized_name, source_ref)
               VALUES (?, ?, ?) ON CONFLICT(canonical_name) DO UPDATE SET
               normalized_name=excluded.normalized_name,
               source_ref=excluded.source_ref""",
            (name, normalize_name(name), row.get("source_ref") or None),
        )
    return len(rows)


def import_hitos(connection: sqlite3.Connection, path: str | Path) -> int:
    rows = _rows(path, {"canonical_name", "source_address"})
    for row in rows:
        connection.execute(
            """INSERT INTO hitos (canonical_name, source_address, source_ref)
               VALUES (?, ?, ?) ON CONFLICT(canonical_name) DO UPDATE SET
               source_address=excluded.source_address,
               source_ref=excluded.source_ref""",
            (row["canonical_name"].strip(), row["source_address"].strip(),
             row.get("source_ref") or None),
        )
    return len(rows)
