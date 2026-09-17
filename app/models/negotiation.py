import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.application import Application


def _utcnow() -> datetime:
    return datetime.now(UTC)


class NegotiationMessage(Base):
    """Сообщение из переговоров с заказчиком по отклику.

    role: "customer" — сообщение заказчика (вставлено владельцем копипастом
    с площадки), "me" — ответ владельца (отправлен на площадку).
    channel: "fl" | "telegram" | "email" — где шла переписка.
    """

    __tablename__ = "negotiation_message"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="fl")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    application: Mapped["Application"] = relationship(
        back_populates="negotiation_messages"
    )
