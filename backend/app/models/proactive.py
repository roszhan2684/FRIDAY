from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ProactiveLog(Base):
    __tablename__ = "proactive_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # meeting_alert|reminder_fire|routine_suggestion
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # NULL=shown, True=yes, False=no
    shown_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now(), index=True)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # wake|stt|llm|tts|embed
    model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BrowserProfile(Base):
    __tablename__ = "browser_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_dir: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("user_id", "profile_dir", name="uq_browser_profile"),
    )


class SyncMetadata(Base):
    __tablename__ = "sync_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_synced: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("user_id", "table_name", name="uq_sync_meta"),
    )


# Memory graph for Phase 5
class MemoryNode(Base):
    __tablename__ = "memory_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # person|place|task|file|site|routine
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    last_mentioned: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())


class MemoryEdge(Base):
    __tablename__ = "memory_edges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("memory_nodes.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), ForeignKey("memory_nodes.id", ondelete="CASCADE"), nullable=False)
    relation: Mapped[str] = mapped_column(String(128), nullable=False)  # works_at|buys_from|frequently_visits
    weight: Mapped[float] = mapped_column(__import__("sqlalchemy").Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())
