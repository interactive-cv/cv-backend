from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.cv_variant import CVVariant
    from app.models.link_hit import LinkHit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShortLink(Base):
    __tablename__ = "short_link"

    code: Mapped[str] = mapped_column(Text, primary_key=True)  # "R8H", uppercase 4-6
    cv_variant_id: Mapped[str] = mapped_column(Uuid, ForeignKey("cv_variant.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_hits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    variant: Mapped["CVVariant"] = relationship(back_populates="links")
    hits: Mapped[list["LinkHit"]] = relationship(back_populates="link")
