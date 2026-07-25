from datetime import UTC, datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConfigText(Base):
    """Редактируемые через админку тексты: мастер-CV, README, промпты.

    Key-value хранилище. Ключи (см. KEYS ниже):
      - master_cv: публичный мастер-CV (чистый markdown, без TODO/комментариев).
        Синхронно обновляет master_cv.full_markdown при сохранении.
      - readme: README для GitHub-профиля владельца (пуш в GitHub вручную).
      - prompt_chat: системный промпт HR-чата (плейсхолдеры {name}, {cv_markdown}).
      - prompt_generate: промпт генерации отклика ({cv_markdown}, {vacancy_text},
        {selected_projects}, {cv_link}).
      - prompt_cv_edit: промпт AI-правки мастер-CV ({current_cv}, {instruction}).

    Seed создаёт записи только при первом запуске (если ключей нет).
    """

    __tablename__ = "config_text"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


# Допустимые ключи (для валидации в API и seed).
CONFIG_KEYS = [
    "master_cv",
    "readme",
    "prompt_chat",
    "prompt_generate",
    "prompt_generate_freelance",
    "prompt_generate_contest",
    "prompt_cv_edit",
    "prompt_response_edit",
]
