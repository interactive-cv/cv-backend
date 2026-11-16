"""Хелперы для чтения/записи системных настроек (AppSetting).

В отличие от ConfigText (редактируемые тексты), AppSetting — служебные
key-value значения, управляемые контролами админки (выбор LLM-модели и т.п.).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting


async def get_app_setting(session: AsyncSession, key: str) -> str | None:
    """Возвращает значение по ключу или None, если записи нет в БД."""
    row = (
        await session.execute(select(AppSetting).where(AppSetting.key == key))
    ).scalar_one_or_none()
    return row.value if row else None


async def set_app_setting(session: AsyncSession, key: str, value: str) -> None:
    """Создаёт или обновляет значение по ключу (flush без commit)."""
    row = (
        await session.execute(select(AppSetting).where(AppSetting.key == key))
    ).scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    await session.flush()
