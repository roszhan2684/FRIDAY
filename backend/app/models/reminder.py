from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    place: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="reminders")


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item: Mapped[str] = mapped_column(String(256), nullable=False)
    store: Mapped[str] = mapped_column(String(128), default="")
    quantity: Mapped[str] = mapped_column(String(64), default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())

    user: Mapped["User"] = relationship(back_populates="shopping_items")


class Errand(Base):
    __tablename__ = "errands"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    place: Mapped[str | None] = mapped_column(String(256), nullable=True)
    due_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=__import__("sqlalchemy").func.now())

    user: Mapped["User"] = relationship(back_populates="errands")


from app.models.user import User  # noqa: E402
