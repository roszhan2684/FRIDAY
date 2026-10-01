from __future__ import annotations
from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="settings")

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
    )


from app.models.user import User  # noqa: E402
