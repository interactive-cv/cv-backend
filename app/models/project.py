import uuid
from typing import Optional

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db import Base, JSONB


class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    short_desc: Mapped[str] = mapped_column(Text)
    long_desc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack: Mapped[list[str]] = mapped_column(JSONB, default=list)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    order_idx: Mapped[int] = mapped_column(Integer, default=0)
