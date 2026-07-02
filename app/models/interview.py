import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.application import Application


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Interview(Base):
    """Этап собеседования по отклику: дата/время + заметки до/после.

    К одному Application может быть привязано несколько интервью (HR-скрин,
    тех-интервью, финал и т.д.).
    """

    __tablename__ = "interview"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application.id"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes_before: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_after: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="interviews")
