import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.short_link import ShortLink


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkHit(Base):
    __tablename__ = "link_hit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    short_link_code: Mapped[str] = mapped_column(ForeignKey("short_link.code"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    referrer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ua: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    link: Mapped["ShortLink"] = relationship(back_populates="hits")
