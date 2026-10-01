"""Interaction events and correction logs CRUD."""
from __future__ import annotations
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.interaction import InteractionEvent, CorrectionLog
from app.config import settings as app_settings

router = APIRouter(prefix="/interactions", tags=["interactions"])


class InteractionIn(BaseModel):
    id: str | None = None
    session_id: str
    transcript: str
    audio_hash: str | None = None
    confidence: float | None = None
    tool_called: str | None = None
    tool_args: dict = {}
    spoken_response: str = ""
    outcome: str = "success"
    error: str | None = None
    duration_ms: int = 0
    timestamp: datetime | None = None


class CorrectionIn(BaseModel):
    id: str | None = None
    audio_hash: str
    bad_transcript: str
    corrected_text: str


@router.get("/")
def get_interactions(limit: int = 50, db: Session = Depends(get_db)):
    rows = (db.query(InteractionEvent)
            .filter_by(user_id=app_settings.friday_user_id)
            .order_by(InteractionEvent.timestamp.desc())
            .limit(limit).all())
    return [{"id": r.id, "transcript": r.transcript, "tool_called": r.tool_called,
             "outcome": r.outcome, "duration_ms": r.duration_ms,
             "timestamp": r.timestamp} for r in rows]


@router.post("/", status_code=201)
def log_interaction(body: InteractionIn, db: Session = Depends(get_db)):
    event = InteractionEvent(
        id=body.id or str(uuid.uuid4()),
        user_id=app_settings.friday_user_id,
        session_id=body.session_id, transcript=body.transcript,
        audio_hash=body.audio_hash, confidence=body.confidence,
        tool_called=body.tool_called, tool_args=body.tool_args,
        spoken_response=body.spoken_response, outcome=body.outcome,
        error=body.error, duration_ms=body.duration_ms,
        timestamp=body.timestamp or datetime.now(),
    )
    db.merge(event)  # upsert by id
    db.commit()
    return {"id": event.id}


corrections_router = APIRouter(prefix="/corrections", tags=["corrections"])


@corrections_router.get("/")
def get_corrections(exported: bool = False, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(CorrectionLog).filter_by(user_id=app_settings.friday_user_id)
    if not exported:
        q = q.filter(CorrectionLog.exported_at.is_(None))
    rows = q.order_by(CorrectionLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "audio_hash": r.audio_hash, "bad_transcript": r.bad_transcript,
             "corrected_text": r.corrected_text, "created_at": r.created_at} for r in rows]


@corrections_router.post("/", status_code=201)
def log_correction(body: CorrectionIn, db: Session = Depends(get_db)):
    c = CorrectionLog(
        id=body.id or str(uuid.uuid4()),
        user_id=app_settings.friday_user_id,
        audio_hash=body.audio_hash,
        bad_transcript=body.bad_transcript,
        corrected_text=body.corrected_text,
    )
    db.merge(c)
    db.commit()
    return {"id": c.id}


@corrections_router.put("/mark-exported")
def mark_exported(ids: list[str], db: Session = Depends(get_db)):
    now = datetime.now()
    db.query(CorrectionLog).filter(CorrectionLog.id.in_(ids)).update(
        {"exported_at": now}, synchronize_session=False
    )
    db.commit()
    return {"marked": len(ids)}
