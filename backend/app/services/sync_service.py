"""Batch sync service — upserts local SQLite records into Postgres.

Accepts a SyncBatch (table name + list of records) and dispatches to the
correct model's upsert logic. Idempotent: records with the same id are
updated, not duplicated.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.interaction import InteractionEvent, CorrectionLog
from app.models.alias import LearnedAlias
from app.models.reminder import Reminder, ShoppingItem, Errand
from app.models.mapping import PersonalMapping, MappingTarget
from app.models.routine import Routine, RoutineStep
from app.models.proactive import ProactiveLog, SyncMetadata

logger = logging.getLogger(__name__)


def sync_batch(db: Session, user_id: str, table: str, records: list[dict]) -> tuple[int, list[str]]:
    """
    Upsert records for the given table.
    Returns (synced_count, error_list).
    """
    handlers = {
        "interaction_events": _sync_interactions,
        "correction_logs": _sync_corrections,
        "learned_aliases": _sync_aliases,
        "reminders": _sync_reminders,
        "shopping_items": _sync_shopping,
        "errands": _sync_errands,
        "personal_mappings": _sync_mappings,
        "routines": _sync_routines,
        "proactive_log": _sync_proactive,
    }
    handler = handlers.get(table)
    if not handler:
        return 0, [f"Unknown table: {table}"]

    synced, errors = handler(db, user_id, records)
    _update_sync_metadata(db, user_id, table, synced)
    return synced, errors


def _update_sync_metadata(db: Session, user_id: str, table: str, count: int):
    meta = db.query(SyncMetadata).filter_by(user_id=user_id, table_name=table).first()
    if meta:
        meta.last_synced_at = datetime.now()
        meta.records_synced = (meta.records_synced or 0) + count
    else:
        db.add(SyncMetadata(user_id=user_id, table_name=table,
                             last_synced_at=datetime.now(), records_synced=count))
    db.commit()


def _sync_interactions(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            obj = InteractionEvent(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                session_id=r.get("session_id", ""), transcript=r.get("transcript", ""),
                audio_hash=r.get("audio_hash"), confidence=r.get("confidence"),
                tool_called=r.get("tool_called"), tool_args=r.get("tool_args", {}),
                spoken_response=r.get("spoken_response", ""),
                outcome=r.get("outcome", "success"), error=r.get("error"),
                duration_ms=r.get("duration_ms", 0),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_corrections(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            obj = CorrectionLog(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                audio_hash=r.get("audio_hash", ""),
                bad_transcript=r.get("bad_transcript", ""),
                corrected_text=r.get("corrected_text", ""),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_aliases(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            existing = db.query(LearnedAlias).filter_by(
                user_id=user_id, phrase=r.get("phrase", "").lower()
            ).first()
            if existing:
                existing.resolved_path = r.get("resolved_path", existing.resolved_path)
                existing.confidence = r.get("confidence", existing.confidence)
                existing.use_count = max(existing.use_count, r.get("use_count", 0))
            else:
                db.add(LearnedAlias(
                    user_id=user_id, phrase=r.get("phrase", "").lower(),
                    resolved_path=r.get("resolved_path", ""),
                    confidence=r.get("confidence", 1.0),
                    use_count=r.get("use_count", 1),
                ))
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_reminders(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            due = None
            if r.get("due_at"):
                try:
                    due = datetime.fromisoformat(r["due_at"][:19])
                except Exception:
                    pass
            obj = Reminder(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                text=r.get("text", ""), raw_input=r.get("raw_input"),
                due_at=due, place=r.get("place"),
                category=r.get("category", "general"),
                status=r.get("status", "pending"),
                follow_up_action=r.get("follow_up_action"),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_shopping(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            obj = ShoppingItem(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                item=r.get("item", ""), store=r.get("store", ""),
                quantity=r.get("quantity", ""), category=r.get("category", ""),
                checked=bool(r.get("checked", False)),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_errands(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            obj = Errand(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                text=r.get("text", ""), place=r.get("place"),
                due_hint=r.get("due_hint"), status=r.get("status", "pending"),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_mappings(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            obj = PersonalMapping(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                trigger_phrase=r.get("trigger_phrase", ""),
                normalized_trigger=r.get("normalized_trigger", r.get("trigger_phrase", "").lower()),
                browser=r.get("browser", "default"),
                browser_profile_email=r.get("browser_profile_email", ""),
                open_mode=r.get("open_mode", "tabs"),
                response_text=r.get("response_text", ""),
                use_count=r.get("use_count", 0),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_routines(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            obj = Routine(
                id=r.get("id", str(uuid.uuid4())), user_id=user_id,
                name=r.get("name", ""), trigger_phrases=r.get("trigger_phrases", []),
                use_count=r.get("use_count", 0),
            )
            db.merge(obj)
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors


def _sync_proactive(db: Session, user_id: str, records: list[dict]) -> tuple[int, list[str]]:
    synced, errors = 0, []
    for r in records:
        try:
            db.add(ProactiveLog(
                user_id=user_id, type=r.get("type", ""),
                payload=r.get("payload"), accepted=r.get("accepted"),
            ))
            synced += 1
        except Exception as exc:
            errors.append(str(exc))
    db.commit()
    return synced, errors
