"""Cloudflare R2 client (S3-compatible via boto3).

Gracefully disabled when R2 credentials are not configured.
All public functions return None / empty list when R2 is not available.
"""
from __future__ import annotations
import logging
from typing import BinaryIO
from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client:
        return _client
    if not settings.r2_configured:
        return None
    try:
        import boto3
        _client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        return _client
    except Exception as exc:
        logger.warning("R2 client init failed: %s", exc)
        return None


def upload_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str | None:
    """Upload bytes to R2. Returns the object key on success, None on failure."""
    client = _get_client()
    if not client:
        logger.debug("R2 not configured — skipping upload for %s", key)
        return None
    try:
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return key
    except Exception as exc:
        logger.error("R2 upload failed (%s/%s): %s", bucket, key, exc)
        return None


def get_presigned_upload_url(bucket: str, key: str, expires: int = 3600) -> str | None:
    client = _get_client()
    if not client:
        return None
    try:
        return client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    except Exception as exc:
        logger.error("R2 presigned upload URL failed: %s", exc)
        return None


def get_presigned_download_url(bucket: str, key: str, expires: int = 3600) -> str | None:
    client = _get_client()
    if not client:
        return None
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    except Exception as exc:
        logger.error("R2 presigned download URL failed: %s", exc)
        return None


def list_objects(bucket: str, prefix: str = "") -> list[dict]:
    client = _get_client()
    if not client:
        return []
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [{"key": obj["Key"], "size": obj["Size"]} for obj in response.get("Contents", [])]
    except Exception as exc:
        logger.error("R2 list failed: %s", exc)
        return []


def delete_object(bucket: str, key: str) -> bool:
    client = _get_client()
    if not client:
        return False
    try:
        client.delete_object(Bucket=bucket, Key=key)
        return True
    except Exception as exc:
        logger.error("R2 delete failed: %s", exc)
        return False
