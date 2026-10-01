"""FRIDAY Backend — FastAPI application entry point.

Exposes:
  GET  /health                   ← liveness check
  All routers at their prefixes

Uses SQLite (local dev) or Postgres (prod via DATABASE_URL).
Auth: Bearer token required on all routes except /health.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import engine
from app.models import Base
from app.auth import verify_api_key
from app.routers.profile import router as profile_router
from app.routers.settings import router as settings_router
from app.routers.mappings import router as mappings_router
from app.routers.routines import router as routines_router
from app.routers.reminders import router as reminders_router
from app.routers.shopping import router as shopping_router, errands_router
from app.routers.interactions import router as interactions_router, corrections_router
from app.routers.aliases import router as aliases_router
from app.routers.sync import router as sync_router
from app.routers.storage import router as storage_router

logging.basicConfig(
    level=logging.DEBUG if settings.friday_backend_debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("friday.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Seed default user profile
    from app.database import db_session
    from app.models.user import User
    with db_session() as db:
        if not db.get(User, settings.friday_user_id):
            db.add(User(
                id=settings.friday_user_id,
                name=settings.friday_user_name,
                email=settings.friday_user_email or None,
            ))
    logger.info("FRIDAY backend ready — DB: %s",
                "postgres" if settings.is_postgres else "sqlite")
    logger.info("R2 storage: %s", "configured" if settings.r2_configured else "not configured")
    yield
    logger.info("FRIDAY backend shutting down")


app = FastAPI(
    title="FRIDAY Backend",
    version="0.1.0",
    description="Cloud backend for FRIDAY personal assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:7700", "http://localhost:7700"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=verify_api_key)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(profile_router)
app.include_router(settings_router)
app.include_router(mappings_router)
app.include_router(routines_router)
app.include_router(reminders_router)
app.include_router(shopping_router)
app.include_router(errands_router)
app.include_router(interactions_router)
app.include_router(corrections_router)
app.include_router(aliases_router)
app.include_router(sync_router)
app.include_router(storage_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "db": "postgres" if settings.is_postgres else "sqlite",
        "r2": settings.r2_configured,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.friday_backend_port,
        reload=settings.friday_backend_debug,
        log_level="debug" if settings.friday_backend_debug else "info",
    )
