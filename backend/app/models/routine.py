from __future__ import annotations
from sqlalchemy import String, Integer, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Routine(Base, TimestampMixin):
    __tablename__ = "routines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    trigger_phrases: Mapped[list] = mapped_column(JSON, default=list)
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="routines")
    steps: Mapped[list["RoutineStep"]] = relationship(back_populates="routine", cascade="all, delete-orphan", order_by="RoutineStep.step_order")


class RoutineStep(Base):
    __tablename__ = "routine_steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    routine_id: Mapped[str] = mapped_column(String(64), ForeignKey("routines.id", ondelete="CASCADE"), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(128), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    spoken_before: Mapped[str] = mapped_column(Text, default="")
    delay_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    step_order: Mapped[int] = mapped_column(Integer, default=0)

    routine: Mapped["Routine"] = relationship(back_populates="steps")


from app.models.user import User  # noqa: E402
