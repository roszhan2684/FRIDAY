"""API key authentication middleware."""
from __future__ import annotations
import json
from fastapi import Request
from starlette.responses import JSONResponse
from app.config import settings

UNPROTECTED = {"/health", "/docs", "/openapi.json", "/redoc"}


async def verify_api_key(request: Request, call_next):
    """Middleware: verify Bearer token on all routes except UNPROTECTED."""
    if request.url.path in UNPROTECTED:
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing API key. Use: Authorization: Bearer <key>"},
        )

    token = auth.removeprefix("Bearer ").strip()
    if token != settings.friday_backend_key:
        return JSONResponse(status_code=401, content={"detail": "Invalid API key."})

    return await call_next(request)
