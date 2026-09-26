"""SQLite storage and schema setup."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path

SCHEMA = files("callejero_generator").joinpath("schema/generator_schema.sql")


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(path: str | Path) -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
