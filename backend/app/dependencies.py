"""Shared FastAPI dependencies."""
from __future__ import annotations
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.config import settings


def ensure_user(db: Session = Depends(get_db)) -> User:
    """Ensure the default user exists. Creates it on first request."""
    user = db.get(User, settings.friday_user_id)
    if not user:
        user = User(
            id=settings.friday_user_id,
            name=settings.friday_user_name,
            email=settings.friday_user_email or None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
