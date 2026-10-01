"""Sync endpoint — bulk upsert from local SQLite to Postgres."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any
from app.database import get_db
from app.services.sync_service import sync_batch
from app.models.proactive import SyncMetadata
from app.config import settings as app_settings

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncBatchRequest(BaseModel):
    table: str
    user_id: str | None = None
    records: list[dict[str, Any]]


class SyncBatchResponse(BaseModel):
    table: str
    synced: int
    errors: list[str] = []


@router.post("/batch", response_model=SyncBatchResponse)
def batch_sync(body: SyncBatchRequest, db: Session = Depends(get_db)):
    user_id = body.user_id or app_settings.friday_user_id
    synced, errors = sync_batch(db, user_id, body.table, body.records)
    return SyncBatchResponse(table=body.table, synced=synced, errors=errors)


@router.get("/status")
def sync_status(db: Session = Depends(get_db)):
    rows = db.query(SyncMetadata).filter_by(user_id=app_settings.friday_user_id).all()
    return {
        "user_id": app_settings.friday_user_id,
        "tables": [{"table": r.table_name, "last_synced_at": r.last_synced_at,
                     "records_synced": r.records_synced} for r in rows],
    }
