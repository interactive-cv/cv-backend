"""Хелперы для чтения/записи редактируемых текстов (ConfigText).

Используются промптами (чтение шаблона из БД с fallback на кодовую константу)
и админ-endpoint'ами (GET/PATCH настроек).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConfigText


async def get_config_value(session: AsyncSession, key: str) -> str | None:
    """Возвращает значение по ключу или None, если ключа нет в БД."""
    row = (
        await session.execute(select(ConfigText).where(ConfigText.key == key))
    ).scalar_one_or_none()
    return row.value if row else None


async def set_config_value(session: AsyncSession, key: str, value: str) -> None:
    """Создаёт или обновляет значение по ключу."""
    row = (
        await session.execute(select(ConfigText).where(ConfigText.key == key))
    ).scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(ConfigText(key=key, value=value))
    await session.flush()


async def get_all_config(session: AsyncSession) -> dict[str, ConfigText]:
    """Все записи ConfigText как dict {key: row}. Для GET /settings."""
    rows = (await session.execute(select(ConfigText))).scalars().all()
    return {r.key: r for r in rows}
