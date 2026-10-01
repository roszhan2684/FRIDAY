"""SQLAlchemy engine and session factory.

Supports both SQLite (local dev) and Postgres (production via Neon).
DATABASE_URL in .env controls which is used.
"""
from __future__ import annotations
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# SQLite needs WAL mode and foreign keys enabled
connect_args = {}
if not settings.is_postgres:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.friday_backend_debug,
)

# Enable WAL + foreign keys for SQLite
if not settings.is_postgres:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for use outside FastAPI (scripts, sync tasks)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
