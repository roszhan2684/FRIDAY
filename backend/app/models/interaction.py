from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class InteractionEvent(Base):
    __tablename__ = "interaction_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    audio_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_called: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tool_args: Mapped[dict] = mapped_column(JSON, default=dict)
    spoken_response: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String(32), default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now(), index=True)


class CorrectionLog(Base):
    __tablename__ = "correction_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    audio_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bad_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())
