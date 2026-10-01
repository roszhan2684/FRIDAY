"""User profile CRUD."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    timezone: str | None = None
    wake_word: str | None = None
    tts_voice: str | None = None
    tts_style: str | None = None


def _ensure_user(db: Session) -> User:
    user = db.get(User, settings.friday_user_id)
    if not user:
        user = User(
            id=settings.friday_user_id,
            name=settings.friday_user_name,
            email=settings.friday_user_email,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/")
def get_profile(db: Session = Depends(get_db)):
    return _ensure_user(db)


@router.put("/")
def update_profile(update: ProfileUpdate, db: Session = Depends(get_db)):
    user = _ensure_user(db)
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
