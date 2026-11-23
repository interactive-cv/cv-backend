"""Эффективные настройки LLM: модель и уровень рассуждений для всех вызовов z.ai.

Хранятся в app_setting (запись создаётся при первом изменении из админки);
отсутствие записи = поведение по умолчанию:
  - модель — из env ZAI_MODEL (settings.zai_model);
  - reasoning_effort — DEFAULT_REASONING_EFFORT ("max"); значение отправляется
    в API явно при каждом вызове.

Читается на каждый вызов stream_chat — настройка применяется ко всем LLM-операциям
(генерация откликов, диалоги, ассистент, HR-чат) без перезапуска.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import async_session
from app.models import AppSetting

logger = logging.getLogger(__name__)

# Доступные модели (переключатель в админке; пополняется по мере появления).
ALLOWED_LLM_MODELS: list[str] = ["glm-5.4", "glm-5.3-flash"]

# Уровни рассуждений (docs.z.ai: reasoning_effort, glm-5.4/5.3-flash).
# От слабого к сильному — порядок важен для UI-слайдера.
ALLOWED_REASONING_EFFORTS: list[str] = ["low", "high", "max"]

# Дефолтный уровень; значение всегда уходит в API явно.
DEFAULT_REASONING_EFFORT = "max"

LLM_MODEL_KEY = "llm_model"
LLM_REASONING_KEY = "llm_reasoning_effort"

_SETTING_KEYS = (LLM_MODEL_KEY, LLM_REASONING_KEY)


def resolve_llm_settings(saved: dict[str, str]) -> tuple[str, str]:
    """(model, reasoning_effort) из сохранённых значений + дефолты.

    saved — {key: value} записей app_setting. Неизвестные/недопустимые
    значения игнорируются (fallback на дефолт).
    """
    model = settings.zai_model
    effort = DEFAULT_REASONING_EFFORT
    if saved.get(LLM_MODEL_KEY) in ALLOWED_LLM_MODELS:
        model = saved[LLM_MODEL_KEY]
    if saved.get(LLM_REASONING_KEY) in ALLOWED_REASONING_EFFORTS:
        effort = saved[LLM_REASONING_KEY]
    return model, effort


async def _load_saved(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.execute(select(AppSetting).where(AppSetting.key.in_(_SETTING_KEYS)))
    ).scalars().all()
    return {r.key: r.value for r in rows}


async def get_llm_settings_from_session(session: AsyncSession) -> tuple[str, str]:
    """Эффективные настройки через сессию запроса (для GET-эндпоинта админки)."""
    return resolve_llm_settings(await _load_saved(session))


async def get_effective_llm_settings() -> tuple[str, str]:
    """Эффективные настройки для stream_chat (у него нет сессии запроса).

    Открывает короткую собственную сессию. При любой ошибке чтения (нет
    таблицы, недоступна БД) — тихо откатывается на дефолты, чтобы LLM
    продолжал работать.
    """
    try:
        async with async_session() as session:
            return resolve_llm_settings(await _load_saved(session))
    except Exception:
        logger.warning("app_setting недоступна, LLM работает на дефолтах", exc_info=True)
        return settings.zai_model, DEFAULT_REASONING_EFFORT
