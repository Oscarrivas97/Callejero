"""Source-specific extraction of the supplied Espacios and Hitos PDF tables."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pdfplumber

from .normalization import normalize_name


@dataclass(frozen=True)
class SourceRow:
    name: str
    address: str | None
    page: int
    row: int


def _cell(value: str | None) -> str:
    return " ".join((value or "").split())


def extract_espacios(path: str | Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages, 1):
            for table in page.extract_tables():
                for row_number, cells in enumerate(table, 1):
                    if len(cells) != 2 or _cell(cells[1]):
                        raise ValueError(f"Unexpected Espacios table shape on page {page_number}")
                    name = _cell(cells[0])
                    if name == "Nombre":
                        continue
                    if not name:
                        raise ValueError(f"Blank Espacio on page {page_number}, row {row_number}")
                    rows.append(SourceRow(name, None, page_number, row_number))
    _require_unique(rows, "Espacio")
    return rows


def extract_hitos(path: str | Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages, 1):
            tables = page.extract_tables()
            if len(tables) != 1:
                raise ValueError(f"Expected one Hitos table on page {page_number}")
            for row_number, cells in enumerate(tables[0], 1):
                if len(cells) != 2:
                    raise ValueError(f"Unexpected Hitos table shape on page {page_number}")
                name, address = map(_cell, cells)
                if (name, address) == ("Nombre", "Dirección"):
                    continue
                if not name or not address:
                    raise ValueError(f"Blank Hito field on page {page_number}, row {row_number}")
                rows.append(SourceRow(name, address, page_number, row_number))
    _require_unique(rows, "Hito")
    return rows


def _require_unique(rows: list[SourceRow], label: str) -> None:
    if not rows:
        raise ValueError(f"No {label} rows extracted")
    seen: set[str] = set()
    for row in rows:
        if row.name in seen:
            raise ValueError(f"Duplicate {label}: {row.name}")
        seen.add(row.name)


def _version(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def import_pdf_sources(connection: sqlite3.Connection, espacios_path: str | Path,
                       hitos_path: str | Path) -> tuple[int, int]:
    """Preflight both PDFs, then upsert source rows without resetting review decisions."""
    espacios = extract_espacios(espacios_path)
    hitos = extract_hitos(hitos_path)
    for row in espacios:
        connection.execute(
            """INSERT INTO espacios (canonical_name, normalized_name, source_ref)
               VALUES (?, ?, ?) ON CONFLICT(canonical_name) DO UPDATE SET
               normalized_name=excluded.normalized_name,
               source_ref=excluded.source_ref""",
            (row.name, normalize_name(row.name), f"{Path(espacios_path).name}:p{row.page}:r{row.row}"),
        )
    for row in hitos:
        connection.execute(
            """INSERT INTO hitos (canonical_name, source_address, source_ref)
               VALUES (?, ?, ?) ON CONFLICT(canonical_name) DO UPDATE SET
               source_address=excluded.source_address,
               source_ref=excluded.source_ref""",
            (row.name, row.address, f"{Path(hitos_path).name}:p{row.page}:r{row.row}"),
        )
    now = datetime.now(UTC).isoformat()
    connection.executemany(
        """INSERT INTO source_imports (source_type, filename, sha256, row_count, imported_at)
           VALUES (?, ?, ?, ?, ?)""",
        [
            ("ESPACIOS", Path(espacios_path).name, _version(espacios_path), len(espacios), now),
            ("HITOS", Path(hitos_path).name, _version(hitos_path), len(hitos), now),
        ],
    )
    return len(espacios), len(hitos)
