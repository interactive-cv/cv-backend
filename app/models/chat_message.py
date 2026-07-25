import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ChatSession(Base):
    """Сессия HR-чата. Один посетитель (browser cookie) = одна сессия.

    Привязка к отклику: short_link_code если чат открыт со страницы CV-варианта.
    TTL: сессии старше chat_ttl_hours (default 24) удаляются lazy-cleanup.
    """

    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    visitor_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_link_code: Mapped[str | None] = mapped_column(
        Text, ForeignKey("short_link.code"), nullable=True
    )
    # Флаг: сессия принадлежит владельцу (админу). Устанавливается
    # при наличии X-Admin-Token в запросе к /api/chat.
    is_admin: Mapped[bool] = mapped_column(default=False)
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
