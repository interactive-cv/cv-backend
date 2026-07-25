import hashlib
import hmac
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.errors import AppError
from app.models import LinkHit, ShortLink


def hash_ip(ip: str) -> str:
    """HMAC-хэш IP с секретом (приватность: сырые IP не храним, §10)."""
    return hmac.new(
        settings.ip_hash_secret.encode(), ip.encode(), hashlib.sha256
    ).hexdigest()


async def resolve_link(
    code: str, ip: str, ua: str, referrer: str, session: AsyncSession,
    chat_session_id: uuid.UUID | None = None,
) -> tuple[str, datetime]:
    """Резолв короткой ссылки. Возвращает (slug, expires_at) или бросает AppError.

    Проверяет: существование (404), срок (410 gone), лимит кликов (410 gone).
    Побочно: инкрементирует hit_count, пишет link_hit (ip_hash, session_id).
    """
    link = (
        await session.execute(
            select(ShortLink).where(ShortLink.code == code).options(selectinload(ShortLink.variant))
        )
    ).scalar_one_or_none()
    if not link:
        raise AppError("not_found", "Ссылка не найдена", 404)
    # SQLite теряет tzinfo при чтении; приводим к aware для корректного сравнения.
    expires = link.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires:
        raise AppError("gone", "Срок действия ссылки истёк. Свяжитесь с автором.", 410)
    if link.max_hits is not None and link.hit_count >= link.max_hits:
        raise AppError("gone", "Лимит открытий ссылки исчерпан", 410)

    # Атомарный инкремент с guard'ом + LinkHit с session_id.
    session.add(LinkHit(
        short_link_code=link.code,
        referrer=referrer,
        ua=ua,
        ip_hash=hash_ip(ip),
        session_id=chat_session_id,
    ))
    result = await session.execute(
        update(ShortLink)
        .where(ShortLink.code == code)
        .where(
            (ShortLink.max_hits.is_(None))
            | (ShortLink.hit_count < ShortLink.max_hits)
        )
        .values(hit_count=ShortLink.hit_count + 1)
    )
    if result.rowcount == 0:
        await session.rollback()
        raise AppError("gone", "Лимит открытий ссылки исчерпан", 410)
    await session.commit()

    return link.variant.slug, expires
