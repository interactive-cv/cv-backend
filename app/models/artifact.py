import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db import Base

if TYPE_CHECKING:
    from app.models.application import Application


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Artifact(Base):
    """Файл-артефакт конкурсного отклика (APK, видео, исходники и т.д.).

    К одному Application можно прикрепить несколько артефактов.
    Публичная ссылка вида /dl/{code} — живёт, пока отклик не архивирован/удалён.
    """

    __tablename__ = "artifact"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application.id", ondelete="CASCADE"), nullable=False
    )
    # 6-символьный код для публичной ссылки /dl/{code}
    code: Mapped[str] = mapped_column(Text, unique=True, index=True)
    # Оригинальное имя файла ("clapgo.apk") — санитизируется при загрузке
    filename: Mapped[str] = mapped_column(Text)
    # Путь на диске ("artifacts/{app_id}/{code}_{filename}")
    stored_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Аналитика скачиваний (атомарный инкремент, как hit_count у short_link)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    application: Mapped["Application"] = relationship(back_populates="artifacts")
