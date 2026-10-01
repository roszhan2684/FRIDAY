"""Personal mappings (custom command registry) CRUD."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.mapping import PersonalMapping, MappingTarget
from app.config import settings as app_settings

router = APIRouter(prefix="/mappings", tags=["mappings"])


class TargetIn(BaseModel):
    target_type: str = "url"
    target_value: str
    launch_order: int = 0
    window_group: int = 1
    delay_seconds: float = 0.5
    open_mode: str = "tab"


class MappingIn(BaseModel):
    trigger_phrase: str
    normalized_trigger: str | None = None
    browser: str = "default"
    browser_profile_dir: str = ""
    browser_profile_email: str = ""
    open_mode: str = "tabs"
    confirmation_mode: str = "none"
    response_text: str = ""
    targets: list[TargetIn] = []


def _normalize(phrase: str) -> str:
    import re
    s = phrase.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s)


@router.get("/")
def list_mappings(db: Session = Depends(get_db)):
    rows = db.query(PersonalMapping).filter_by(user_id=app_settings.friday_user_id).all()
    return [{"id": r.id, "trigger_phrase": r.trigger_phrase, "browser_profile_email": r.browser_profile_email,
             "use_count": r.use_count, "targets": [{"type": t.target_type, "value": t.target_value,
             "window_group": t.window_group} for t in r.targets]} for r in rows]


@router.post("/", status_code=201)
def create_mapping(body: MappingIn, db: Session = Depends(get_db)):
    norm = body.normalized_trigger or _normalize(body.trigger_phrase)
    existing = db.query(PersonalMapping).filter_by(normalized_trigger=norm).first()
    if existing:
        # Update in place
        mapping = existing
        for field in ("browser", "browser_profile_dir", "browser_profile_email",
                      "open_mode", "confirmation_mode", "response_text"):
            setattr(mapping, field, getattr(body, field))
        db.query(MappingTarget).filter_by(mapping_id=mapping.id).delete()
    else:
        mapping = PersonalMapping(
            id=str(uuid.uuid4()), user_id=app_settings.friday_user_id,
            trigger_phrase=body.trigger_phrase, normalized_trigger=norm,
            browser=body.browser, browser_profile_dir=body.browser_profile_dir,
            browser_profile_email=body.browser_profile_email,
            open_mode=body.open_mode, confirmation_mode=body.confirmation_mode,
            response_text=body.response_text,
        )
        db.add(mapping)

    for t in body.targets:
        db.add(MappingTarget(
            id=str(uuid.uuid4()), mapping_id=mapping.id,
            target_type=t.target_type, target_value=t.target_value,
            launch_order=t.launch_order, window_group=t.window_group,
            delay_seconds=t.delay_seconds, open_mode=t.open_mode,
        ))
    db.commit()
    db.refresh(mapping)
    return {"id": mapping.id, "trigger_phrase": mapping.trigger_phrase}


@router.get("/{mapping_id}")
def get_mapping(mapping_id: str, db: Session = Depends(get_db)):
    m = db.get(PersonalMapping, mapping_id)
    if not m:
        raise HTTPException(404, "Mapping not found")
    return {"id": m.id, "trigger_phrase": m.trigger_phrase, "browser": m.browser,
            "browser_profile_email": m.browser_profile_email, "response_text": m.response_text,
            "targets": [{"type": t.target_type, "value": t.target_value,
                         "order": t.launch_order, "window_group": t.window_group} for t in m.targets]}


@router.delete("/{mapping_id}")
def delete_mapping(mapping_id: str, db: Session = Depends(get_db)):
    m = db.get(PersonalMapping, mapping_id)
    if not m:
        raise HTTPException(404, "Mapping not found")
    db.delete(m)
    db.commit()
    return {"deleted": mapping_id}
