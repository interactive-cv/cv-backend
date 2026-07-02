import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.interview import Interview


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class Application(Base):
    """Отклик на вакансию: объединяет CV, cover letter, ссылку и аналитику."""

    __tablename__ = "application"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    vacancy_text: Mapped[str] = mapped_column(Text)
    cover_letter_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, index=True)
    cv_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("cv_variant.id"), nullable=True
    )
    short_link_code: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("short_link.code"), nullable=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus, name="applicationstatus"),
        default=ApplicationStatus.draft,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    interviews: Mapped[list["Interview"]] = relationship(back_populates="application")
