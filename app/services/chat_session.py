"""Сервис работы с сессиями HR-чата.

Создание/загрузка сессий, сохранение сообщений, lazy-cleanup (TTL).
"""
import hashlib
import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ChatMessage, ChatSession

# TTL сессий в часах (по умолчанию 24).
CHAT_TTL_HOURS = 24

# Сколько последних сообщений передавать в LLM как контекст.
MAX_CONTEXT_MESSAGES = 10

# Regex для извлечения имени/email из сообщения HR.
_NAME_PATTERNS = [
    re.compile(r"(?:меня зовут|я\s+)\s*([А-Яа-яЁё]{2,}\s*[А-Яа-яЁё]{2,})", re.IGNORECASE),
    re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"),
]


def hash_ip(ip: str) -> str:
    """HMAC-хэш IP (тот же алгоритм что в link_hit)."""
    return hmac.new(
        settings.ip_hash_secret.encode(), ip.encode(), hashlib.sha256
    ).hexdigest()


def extract_visitor_name(message: str) -> str | None:
    """Пытается извлечь имя/email из сообщения HR (regex, не LLM)."""
    for pattern in _NAME_PATTERNS:
        m = pattern.search(message)
        if m:
            return m.group(1).strip()[:100]
    return None


async def get_or_create_session(
    session: AsyncSession,
    session_id: str | None,
    ip: str,
    short_link_code: str | None = None,
) -> ChatSession:
    """Загружает сессию по session_id или создаёт новую."""
    if session_id:
        try:
            sid = uuid.UUID(session_id)
            existing = (
                await session.execute(
                    select(ChatSession).where(ChatSession.id == sid)
                )
            ).scalar_one_or_none()
            if existing:
                # Обновляем last_active и short_link_code если появился
                existing.last_active_at = datetime.now(timezone.utc)
                if short_link_code and not existing.short_link_code:
                    existing.short_link_code = short_link_code
                await session.flush()
                return existing
        except (ValueError, Exception):
            pass  # невалидный session_id — создаём новую

    # Новая сессия
    new_session = ChatSession(
        id=uuid.uuid4(),
        ip_hash=hash_ip(ip),
        short_link_code=short_link_code,
    )
    session.add(new_session)
    await session.flush()
    return new_session


async def save_message(
    session: AsyncSession,
    chat_session: ChatSession,
    role: str,
    content: str,
) -> ChatMessage:
    """Сохраняет сообщение в БД."""
    msg = ChatMessage(
        session_id=chat_session.id,
        role=role,
        content=content,
    )
    session.add(msg)
    chat_session.last_active_at = datetime.now(timezone.utc)
    await session.flush()
    return msg


async def load_context_messages(
    session: AsyncSession,
    chat_session: ChatSession,
) -> list[dict]:
    """Загружает последние N сообщений сессии для контекста LLM."""
    msgs = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(MAX_CONTEXT_MESSAGES)
        )
    ).scalars().all()
    # Разворачиваем в хронологическом порядке
    msgs = list(reversed(msgs))
    return [{"role": m.role, "content": m.content} for m in msgs]


async def cleanup_old_sessions(session: AsyncSession) -> int:
    """Удаляет сессии старше CHAT_TTL_HOURS. Возвращает кол-во удалённых."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CHAT_TTL_HOURS)
    result = await session.execute(
        delete(ChatSession).where(ChatSession.last_active_at < cutoff)
    )
    return result.rowcount or 0
