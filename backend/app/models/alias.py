from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LearnedAlias(Base):
    __tablename__ = "learned_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    phrase: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    resolved_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("user_id", "phrase", name="uq_alias_user_phrase"),
    )


class FileReference(Base):
    __tablename__ = "file_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    alias: Mapped[str | None] = mapped_column(String(256), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    last_opened: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
