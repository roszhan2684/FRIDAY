"""Cloudflare R2 presigned URL endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.r2 import get_presigned_upload_url, get_presigned_download_url, list_objects
from app.config import settings

router = APIRouter(prefix="/storage", tags=["storage"])


class UploadUrlRequest(BaseModel):
    bucket: str
    key: str
    expires: int = 3600


class DownloadUrlRequest(BaseModel):
    bucket: str
    key: str
    expires: int = 3600


@router.post("/upload-url")
def get_upload_url(body: UploadUrlRequest):
    if not settings.r2_configured:
        raise HTTPException(503, "R2 storage not configured. Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY in .env")
    url = get_presigned_upload_url(body.bucket, body.key, body.expires)
    if not url:
        raise HTTPException(500, "Failed to generate upload URL")
    return {"url": url, "key": body.key}


@router.post("/download-url")
def get_download_url(body: DownloadUrlRequest):
    if not settings.r2_configured:
        raise HTTPException(503, "R2 storage not configured")
    url = get_presigned_download_url(body.bucket, body.key, body.expires)
    if not url:
        raise HTTPException(500, "Failed to generate download URL")
    return {"url": url, "key": body.key}


@router.get("/list")
def list_bucket_objects(bucket: str, prefix: str = ""):
    if not settings.r2_configured:
        return {"objects": [], "r2_configured": False}
    objects = list_objects(bucket, prefix)
    return {"objects": objects, "count": len(objects)}
