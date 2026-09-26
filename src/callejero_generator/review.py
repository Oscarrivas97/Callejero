"""Manual review transitions and strict approved-question export."""

import json
import sqlite3
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from . import __version__
from .routes import Option, check_question
from .settings import QualitySettings

APP_SCHEMA = files("callejero_generator").joinpath("schema/app_export_schema.sql")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def review_question(connection: sqlite3.Connection, question_id: int, action: str,
                    note: str = "") -> None:
    if action not in {"APPROVED", "REJECTED"}:
        raise ValueError("Action must be APPROVED or REJECTED")
    row = connection.execute("SELECT status FROM questions WHERE id=?", (question_id,)).fetchone()
    if row is None:
        raise ValueError("Question does not exist")
    if row["status"] != "READY_FOR_REVIEW":
        raise ValueError("Only READY_FOR_REVIEW questions may be reviewed")
    now = _utc_now()
    connection.execute(
        "UPDATE questions SET status=?, reviewed_at=?, reviewer_note=? WHERE id=?",
        (action, now, note, question_id),
    )
    connection.execute(
        "INSERT INTO review_history (question_id, action, note, created_at) VALUES (?, ?, ?, ?)",
        (question_id, action, note, now),
    )


def _validated_export_rows(connection: sqlite3.Connection, settings: QualitySettings) -> list[tuple[sqlite3.Row, list[sqlite3.Row]]]:
    questions = connection.execute(
        "SELECT * FROM questions WHERE status='APPROVED' ORDER BY id"
    ).fetchall()
    result = []
    for question in questions:
        options = connection.execute(
            "SELECT * FROM question_options WHERE question_id=? ORDER BY option_letter",
            (question["id"],),
        ).fetchall()
        checked = check_question(question["question_type"], [
            Option(option["option_letter"], tuple(json.loads(option["display_sequence_json"])),
                   bool(option["is_valid"]), option["estimated_time_s"])
            for option in options
        ], minimum_espacios=settings.minimum_espacios,
            min_advantage_ratio=settings.min_advantage_ratio,
            min_advantage_seconds=settings.min_advantage_seconds)
        if not checked.accepted or checked.correct_option != question["correct_option"]:
            raise ValueError(f"Approved question {question['id']} failed validation: {checked.reason}")
        if [option["option_letter"] for option in options if option["is_correct"]] != [checked.correct_option]:
            raise ValueError(f"Approved question {question['id']} has inconsistent correct-option flags")
        all_ids = {item for option in options for item in json.loads(option["display_sequence_json"])}
        if all_ids:
            placeholders = ",".join("?" for _ in all_ids)
            found = connection.execute(
                f"SELECT id FROM espacios WHERE active=1 AND id IN ({placeholders})", tuple(all_ids)
            ).fetchall()
            if len(found) != len(all_ids):
                raise ValueError(f"Question {question['id']} contains unknown Espacios")
        result.append((question, options))
    return result


def export_approved(connection: sqlite3.Connection, destination: str | Path,
                    settings: QualitySettings | None = None,
                    config_hash: str | None = None) -> int:
    """Validate all approved rows before creating the app database."""
    settings = settings or QualitySettings(6, 0.05, 30)
    selected = _validated_export_rows(connection, settings)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temporary) as app:
            app.execute("PRAGMA foreign_keys = ON")
            app.executescript(APP_SCHEMA.read_text(encoding="utf-8"))
            runs = [dict(row) for row in connection.execute(
                """SELECT DISTINCT r.* FROM generator_runs r JOIN questions q
                   ON q.generator_run_id=r.id WHERE q.status='APPROVED' ORDER BY r.id"""
            )]
            metadata = {
                "schema_version": "1",
                "generator_version": __version__,
                "config_hash": config_hash or "unknown",
                "generator_runs_json": json.dumps(runs, ensure_ascii=False, sort_keys=True),
            }
            app.executemany("INSERT INTO export_metadata (key, value) VALUES (?, ?)",
                            metadata.items())
            used_hitos = {q[column] for q, _ in selected
                          for column in ("origin_hito_id", "destination_hito_id")}
            for hito_id in sorted(used_hitos):
                hito = connection.execute("SELECT canonical_name FROM hitos WHERE id=?",
                                          (hito_id,)).fetchone()
                app.execute("INSERT INTO hitos (id, name) VALUES (?, ?)",
                            (hito_id, hito["canonical_name"]))
            for question, options in selected:
                app.execute(
                    """INSERT INTO questions (id, type, origin_hito_id, destination_hito_id,
                       wording, difficulty, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (question["id"], question["question_type"], question["origin_hito_id"],
                     question["destination_hito_id"], question["wording"],
                     question["difficulty"], question["correct_option"]),
                )
                for option in options:
                    ids = json.loads(option["display_sequence_json"])
                    names = [connection.execute("SELECT canonical_name FROM espacios WHERE id=?",
                                                (item,)).fetchone()["canonical_name"] for item in ids]
                    app.execute(
                        """INSERT INTO question_options
                           (question_id, option_letter, route_text, route_json)
                           VALUES (?, ?, ?, ?)""",
                        (question["id"], option["option_letter"], " → ".join(names),
                         json.dumps(names, ensure_ascii=False)),
                    )
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return len(selected)
