"""Settings CRUD (key-value preferences)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.settings import Setting
from app.config import settings as app_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("/")
def get_all_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).filter_by(user_id=app_settings.friday_user_id).all()
    return {r.key: r.value for r in rows}


@router.get("/{key}")
def get_setting(key: str, db: Session = Depends(get_db)):
    row = db.query(Setting).filter_by(user_id=app_settings.friday_user_id, key=key).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": row.key, "value": row.value}


@router.put("/{key}")
def upsert_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    row = db.query(Setting).filter_by(user_id=app_settings.friday_user_id, key=key).first()
    if row:
        row.value = body.value
    else:
        row = Setting(user_id=app_settings.friday_user_id, key=key, value=body.value)
        db.add(row)
    db.commit()
    return {"key": key, "value": body.value}


@router.delete("/{key}")
def delete_setting(key: str, db: Session = Depends(get_db)):
    row = db.query(Setting).filter_by(user_id=app_settings.friday_user_id, key=key).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    db.delete(row)
    db.commit()
    return {"deleted": key}
