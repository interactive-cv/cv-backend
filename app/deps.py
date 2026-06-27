from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.errors import AppError

engine = create_async_engine(settings.async_database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


async def require_admin(authorization: Annotated[str, Header()]) -> str:
    if authorization != f"Bearer {settings.admin_token}":
        raise AppError("unauthorized", "Неверный админ-токен", 401)
    return authorization
