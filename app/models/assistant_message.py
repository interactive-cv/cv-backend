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


class AssistantMessage(Base):
    """Сообщение треда владельца с LLM-ассистентом по отклику.

    Отдельно от переговоров (negotiation_message): это внутренний диалог
    «владелец ↔ ассистент» — вопросы по заказу, тактика, подготовка
    ответов заказчику. role: "user" | "assistant".
    """

    __tablename__ = "assistant_message"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    application: Mapped["Application"] = relationship(
        back_populates="assistant_messages"
    )
