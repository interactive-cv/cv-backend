import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.master_cv import MasterCV
    from app.models.short_link import ShortLink


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CVVariantStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class CVVariant(Base):
    __tablename__ = "cv_variant"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    master_cv_id: Mapped[int] = mapped_column(ForeignKey("master_cv.id"))
    slug: Mapped[str] = mapped_column(Text, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text)
    vacancy_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CVVariantStatus] = mapped_column(
        SAEnum(CVVariantStatus, name="cvvariantstatus"), default=CVVariantStatus.draft
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    master: Mapped["MasterCV"] = relationship(back_populates="variants")
    links: Mapped[list["ShortLink"]] = relationship(back_populates="variant")
