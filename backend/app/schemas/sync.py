"""Schemas for the sync endpoint."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class SyncRecord(BaseModel):
    id: str
    data: dict[str, Any]


class SyncBatch(BaseModel):
    table: str
    user_id: str
    records: list[dict[str, Any]]


class SyncBatchResponse(BaseModel):
    table: str
    synced: int
    errors: list[str] = []


class SyncStatus(BaseModel):
    user_id: str
    tables: list[dict[str, Any]]
