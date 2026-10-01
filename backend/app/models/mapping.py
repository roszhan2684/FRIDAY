from __future__ import annotations
from sqlalchemy import String, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class PersonalMapping(Base, TimestampMixin):
    __tablename__ = "personal_mappings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_phrase: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_trigger: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    browser: Mapped[str] = mapped_column(String(32), default="default")
    browser_profile_dir: Mapped[str] = mapped_column(String(128), default="")
    browser_profile_email: Mapped[str] = mapped_column(String(256), default="")
    open_mode: Mapped[str] = mapped_column(String(32), default="tabs")
    confirmation_mode: Mapped[str] = mapped_column(String(32), default="none")
    response_text: Mapped[str] = mapped_column(Text, default="")
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="mappings")
    targets: Mapped[list["MappingTarget"]] = relationship(back_populates="mapping", cascade="all, delete-orphan", order_by="MappingTarget.launch_order")


class MappingTarget(Base):
    __tablename__ = "mapping_targets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mapping_id: Mapped[str] = mapped_column(String(64), ForeignKey("personal_mappings.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)  # url|file|folder|app
    target_value: Mapped[str] = mapped_column(Text, nullable=False)
    launch_order: Mapped[int] = mapped_column(Integer, default=0)
    window_group: Mapped[int] = mapped_column(Integer, default=1)
    delay_seconds: Mapped[float] = mapped_column(Float, default=0.5)
    open_mode: Mapped[str] = mapped_column(String(32), default="tab")

    mapping: Mapped["PersonalMapping"] = relationship(back_populates="targets")


from app.models.user import User  # noqa: E402
