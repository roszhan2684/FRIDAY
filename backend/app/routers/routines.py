"""Routines CRUD."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.routine import Routine, RoutineStep
from app.config import settings as app_settings

router = APIRouter(prefix="/routines", tags=["routines"])


class StepIn(BaseModel):
    tool: str
    args: dict = {}
    spoken_before: str = ""
    delay_seconds: float = 0.0
    step_order: int = 0


class RoutineIn(BaseModel):
    name: str
    trigger_phrases: list[str] = []
    steps: list[StepIn] = []


@router.get("/")
def list_routines(db: Session = Depends(get_db)):
    rows = db.query(Routine).filter_by(user_id=app_settings.friday_user_id).all()
    return [{"id": r.id, "name": r.name, "trigger_phrases": r.trigger_phrases,
             "use_count": r.use_count, "steps": len(r.steps)} for r in rows]


@router.post("/", status_code=201)
def create_routine(body: RoutineIn, db: Session = Depends(get_db)):
    routine = Routine(
        id=str(uuid.uuid4()), user_id=app_settings.friday_user_id,
        name=body.name, trigger_phrases=body.trigger_phrases,
    )
    db.add(routine)
    for s in body.steps:
        db.add(RoutineStep(
            id=str(uuid.uuid4()), routine_id=routine.id,
            tool=s.tool, args=s.args, spoken_before=s.spoken_before,
            delay_seconds=s.delay_seconds, step_order=s.step_order,
        ))
    db.commit()
    db.refresh(routine)
    return {"id": routine.id, "name": routine.name}


@router.get("/{routine_id}")
def get_routine(routine_id: str, db: Session = Depends(get_db)):
    r = db.get(Routine, routine_id)
    if not r:
        raise HTTPException(404, "Routine not found")
    return {"id": r.id, "name": r.name, "trigger_phrases": r.trigger_phrases,
            "use_count": r.use_count,
            "steps": [{"tool": s.tool, "args": s.args, "spoken_before": s.spoken_before,
                        "delay_seconds": s.delay_seconds, "order": s.step_order} for s in r.steps]}


@router.put("/{routine_id}")
def update_routine(routine_id: str, body: RoutineIn, db: Session = Depends(get_db)):
    r = db.get(Routine, routine_id)
    if not r:
        raise HTTPException(404, "Routine not found")
    r.name = body.name
    r.trigger_phrases = body.trigger_phrases
    db.query(RoutineStep).filter_by(routine_id=r.id).delete()
    for s in body.steps:
        db.add(RoutineStep(
            id=str(uuid.uuid4()), routine_id=r.id,
            tool=s.tool, args=s.args, spoken_before=s.spoken_before,
            delay_seconds=s.delay_seconds, step_order=s.step_order,
        ))
    db.commit()
    return {"id": r.id, "updated": True}


@router.delete("/{routine_id}")
def delete_routine(routine_id: str, db: Session = Depends(get_db)):
    r = db.get(Routine, routine_id)
    if not r:
        raise HTTPException(404, "Routine not found")
    db.delete(r)
    db.commit()
    return {"deleted": routine_id}
