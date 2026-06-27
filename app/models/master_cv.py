from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONB

if TYPE_CHECKING:
    from app.models.cv_variant import CVVariant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MasterCV(Base):
    __tablename__ = "master_cv"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary: Mapped[str] = mapped_column(Text)
    contacts: Mapped[dict] = mapped_column(JSONB)
    skills_core: Mapped[dict] = mapped_column(JSONB, default=dict)
    skills_familiar: Mapped[dict] = mapped_column(JSONB, default=dict)
    languages: Mapped[dict] = mapped_column(JSONB, default=dict)
    format: Mapped[dict] = mapped_column(JSONB, default=dict)
    full_markdown: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    variants: Mapped[list["CVVariant"]] = relationship(back_populates="master")
