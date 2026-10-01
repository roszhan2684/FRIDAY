"""Reminders, shopping list, and errands CRUD."""
from __future__ import annotations
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.reminder import Reminder, ShoppingItem, Errand
from app.config import settings as app_settings

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderIn(BaseModel):
    text: str
    raw_input: str | None = None
    due_at: datetime | None = None
    place: str | None = None
    category: str = "general"
    follow_up_action: str | None = None


class ReminderUpdate(BaseModel):
    status: str | None = None
    snoozed_until: datetime | None = None
    due_at: datetime | None = None


@router.get("/")
def list_reminders(scope: str = "today", db: Session = Depends(get_db)):
    q = db.query(Reminder).filter_by(user_id=app_settings.friday_user_id)
    if scope == "today":
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        today_end = datetime.now().replace(hour=23, minute=59, second=59)
        q = q.filter(Reminder.status.in_(["pending", "snoozed"]),
                     Reminder.due_at.between(today_start, today_end))
    elif scope == "pending":
        q = q.filter(Reminder.status.in_(["pending", "snoozed"]))
    return [{"id": r.id, "text": r.text, "due_at": r.due_at, "place": r.place,
             "category": r.category, "status": r.status} for r in q.order_by(Reminder.due_at).all()]


@router.post("/", status_code=201)
def create_reminder(body: ReminderIn, db: Session = Depends(get_db)):
    r = Reminder(
        id=str(uuid.uuid4()), user_id=app_settings.friday_user_id,
        text=body.text, raw_input=body.raw_input, due_at=body.due_at,
        place=body.place, category=body.category, follow_up_action=body.follow_up_action,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "text": r.text, "due_at": r.due_at}


@router.put("/{reminder_id}")
def update_reminder(reminder_id: str, body: ReminderUpdate, db: Session = Depends(get_db)):
    r = db.get(Reminder, reminder_id)
    if not r:
        raise HTTPException(404, "Reminder not found")
    if body.status:
        r.status = body.status
        if body.status == "fired":
            r.fired_at = datetime.now()
    if body.snoozed_until:
        r.snoozed_until = body.snoozed_until
        r.due_at = body.snoozed_until
        r.status = "snoozed"
    if body.due_at:
        r.due_at = body.due_at
    db.commit()
    return {"id": reminder_id, "status": r.status}


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: str, db: Session = Depends(get_db)):
    r = db.get(Reminder, reminder_id)
    if not r:
        raise HTTPException(404, "Reminder not found")
    db.delete(r)
    db.commit()
    return {"deleted": reminder_id}
