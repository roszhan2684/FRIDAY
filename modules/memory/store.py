"""Memory store — read/write interface over the SQLite database.

All reads and writes go through this module.
The learner module calls this to update weights.
"""
from __future__ import annotations
import json
from datetime import datetime

from database import db
from shared.schemas import (
    LearnedAlias,
    UserPreference,
    Routine,
    InteractionEvent,
    CorrectionEvent,
)


# ─── Interaction Events ───────────────────────────────────────────────────────

def log_interaction(event: InteractionEvent) -> None:
    db.execute(
        """INSERT INTO interaction_events
           (id, session_id, transcript, audio_hash, confidence, tool_called,
            tool_args, spoken_response, outcome, error, duration_ms, timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event.id, event.session_id, event.transcript, event.audio_hash,
            event.confidence, event.tool_called, json.dumps(event.tool_args),
            event.spoken_response, event.outcome.value, event.error,
            event.duration_ms, event.timestamp.isoformat(),
        ),
    )


def get_recent_transcripts(limit: int = 10) -> list[str]:
    rows = db.fetchall(
        "SELECT transcript FROM interaction_events ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    return [r["transcript"] for r in rows]


# ─── Corrections ─────────────────────────────────────────────────────────────

def log_correction(event: CorrectionEvent) -> None:
    db.execute(
        "INSERT INTO correction_logs(id, audio_hash, bad_transcript, corrected_text, timestamp) VALUES (?,?,?,?,?)",
        (event.id, event.audio_hash, event.bad_transcript, event.corrected_text, event.timestamp.isoformat()),
    )


def get_unexported_corrections(limit: int = 100) -> list[dict]:
    rows = db.fetchall(
        "SELECT * FROM correction_logs WHERE used_in_training = 0 ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def mark_corrections_exported(ids: list[str]) -> None:
    db.executemany(
        "UPDATE correction_logs SET used_in_training = 1 WHERE id = ?",
        [(i,) for i in ids],
    )


# ─── Aliases ─────────────────────────────────────────────────────────────────

def get_all_aliases() -> dict[str, str]:
    rows = db.fetchall("SELECT phrase, resolved_path FROM learned_aliases ORDER BY use_count DESC")
    return {r["phrase"]: r["resolved_path"] for r in rows}


def get_alias(phrase: str) -> str | None:
    row = db.fetchone(
        "SELECT resolved_path FROM learned_aliases WHERE LOWER(phrase) = LOWER(?) LIMIT 1",
        (phrase,),
    )
    return row["resolved_path"] if row else None


def upsert_alias(phrase: str, path: str, confidence: float = 1.0) -> None:
    db.execute(
        """INSERT INTO learned_aliases(phrase, resolved_path, confidence, use_count, last_used, created_at)
           VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))
           ON CONFLICT(phrase) DO UPDATE SET
               resolved_path = excluded.resolved_path,
               confidence = excluded.confidence,
               use_count = use_count + 1,
               last_used = datetime('now')""",
        (phrase.lower().strip(), path, confidence),
    )


# ─── Preferences ─────────────────────────────────────────────────────────────

def get_preference(key: str, default: str | None = None) -> str | None:
    row = db.fetchone("SELECT value FROM preferences WHERE key = ?", (key,))
    return row["value"] if row else default


def set_preference(key: str, value: str) -> None:
    db.execute(
        "INSERT INTO preferences(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
        (key, value),
    )


def get_all_preferences() -> dict[str, str]:
    rows = db.fetchall("SELECT key, value FROM preferences")
    return {r["key"]: r["value"] for r in rows}


# ─── Routines ────────────────────────────────────────────────────────────────

def get_routine(name: str) -> Routine | None:
    row = db.fetchone("SELECT * FROM routines WHERE LOWER(name) = LOWER(?)", (name,))
    if not row:
        return None
    d = dict(row)
    d["trigger_phrases"] = json.loads(d["trigger_phrases"])
    d["steps"] = json.loads(d["steps"])
    return Routine(**d)


def list_routines() -> list[dict]:
    rows = db.fetchall("SELECT id, name, use_count, updated_at FROM routines ORDER BY use_count DESC")
    return [dict(r) for r in rows]


# ─── Audit ───────────────────────────────────────────────────────────────────

def audit(action: str, tool: str | None = None, args: dict | None = None, confirmed: bool = False) -> None:
    db.execute(
        "INSERT INTO audit_log(action, tool, args, confirmed) VALUES (?,?,?,?)",
        (action, tool, json.dumps(args or {}), int(confirmed)),
    )
