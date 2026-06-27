import secrets
from collections.abc import AsyncGenerator
from typing import Annotated, Optional

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.errors import AppError

engine = create_async_engine(settings.async_database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def require_admin(authorization: Annotated[Optional[str], Header()] = None) -> str:
    """Проверка Bearer-токена. Constant-time сравнение, 401 в едином AppError-формате."""
    expected = f"Bearer {settings.admin_token}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise AppError("unauthorized", "Неверный или отсутствующий админ-токен", 401)
    return authorization
