import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChatSession(Base):
    """Сессия HR-чата. Один посетитель (browser cookie) = одна сессия.

    Привязка к отклику: short_link_code если чат открыт со страницы CV-варианта.
    TTL: сессии старше chat_ttl_hours (default 24) удаляются lazy-cleanup.
    """

    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ip_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visitor_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_link_code: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("short_link.code"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    """Сообщение в HR-чате: user (HR) или assistant (LLM)."""

    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_session.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
