"""Learned aliases and file references CRUD."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.alias import LearnedAlias, FileReference
from app.config import settings as app_settings

router = APIRouter(prefix="/aliases", tags=["aliases"])


class AliasUpsert(BaseModel):
    resolved_path: str
    file_type: str = ""
    confidence: float = 1.0


@router.get("/")
def get_aliases(db: Session = Depends(get_db)):
    rows = db.query(LearnedAlias).filter_by(user_id=app_settings.friday_user_id).all()
    return {r.phrase: {"path": r.resolved_path, "confidence": r.confidence,
                        "use_count": r.use_count} for r in rows}


@router.put("/{phrase}")
def upsert_alias(phrase: str, body: AliasUpsert, db: Session = Depends(get_db)):
    phrase_lower = phrase.lower().strip()
    existing = db.query(LearnedAlias).filter_by(
        user_id=app_settings.friday_user_id, phrase=phrase_lower
    ).first()
    if existing:
        existing.resolved_path = body.resolved_path
        existing.confidence = body.confidence
        existing.use_count += 1
    else:
        db.add(LearnedAlias(
            user_id=app_settings.friday_user_id, phrase=phrase_lower,
            resolved_path=body.resolved_path, file_type=body.file_type,
            confidence=body.confidence,
        ))
    db.commit()
    return {"phrase": phrase_lower, "resolved_path": body.resolved_path}


@router.delete("/{phrase}")
def delete_alias(phrase: str, db: Session = Depends(get_db)):
    row = db.query(LearnedAlias).filter_by(
        user_id=app_settings.friday_user_id, phrase=phrase.lower()
    ).first()
    if not row:
        raise HTTPException(404, "Alias not found")
    db.delete(row)
    db.commit()
    return {"deleted": phrase}


@router.delete("/")
def clear_all_aliases(db: Session = Depends(get_db)):
    count = db.query(LearnedAlias).filter_by(user_id=app_settings.friday_user_id).count()
    db.query(LearnedAlias).filter_by(user_id=app_settings.friday_user_id).delete()
    db.commit()
    return {"cleared": count}
