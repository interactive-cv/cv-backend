import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.short_link import ShortLink


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LinkHit(Base):
    __tablename__ = "link_hit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    short_link_code: Mapped[str] = mapped_column(ForeignKey("short_link.code"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ua: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # session_id — единый профиль посетителя (связь с chat_session).
    # Nullable: старые клики (до фичи) не имеют session_id.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("chat_session.id"), nullable=True
    )

    link: Mapped["ShortLink"] = relationship(back_populates="hits")
