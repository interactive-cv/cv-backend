from datetime import UTC, datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AppSetting(Base):
    """Системные настройки (key-value), не являющиеся редактируемыми текстами.

    Отличие от ConfigText: ConfigText — крупные тексты, редактируемые со страницы
    «Настройки»; AppSetting — служебные значения (выбор LLM-модели, уровень
    рассуждений и т.п.), управляемые отдельными контролами админки.

    Ключи:
      - llm_model: модель для всех вызовов z.ai (см. ALLOWED_LLM_MODELS).
      - llm_reasoning_effort: уровень рассуждений (см. ALLOWED_REASONING_EFFORTS).
    Отсутствие записи = «использовать значение по умолчанию» (env / DEFAULT_*).
    """

    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
