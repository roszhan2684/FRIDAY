from __future__ import annotations
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="Boss")
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")
    wake_word: Mapped[str] = mapped_column(String(64), default="hey friday")
    tts_voice: Mapped[str] = mapped_column(String(64), default="en-US-judith")
    tts_style: Mapped[str] = mapped_column(String(64), default="Conversational")

    settings: Mapped[list["Setting"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mappings: Mapped[list["PersonalMapping"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    routines: Mapped[list["Routine"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    shopping_items: Mapped[list["ShoppingItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    errands: Mapped[list["Errand"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# Avoid circular imports
from app.models.settings import Setting  # noqa: E402
from app.models.mapping import PersonalMapping  # noqa: E402
from app.models.routine import Routine  # noqa: E402
from app.models.reminder import Reminder, ShoppingItem, Errand  # noqa: E402
