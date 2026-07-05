import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_session
from app.errors import AppError
from app.llm.client import stream_chat
from app.llm.prompts import build_system_prompt
from app.models import ChatMessage, ChatSession, MasterCV
from app.ratelimit import check_rate_limit
from app.request_utils import client_ip
from app.schemas.chat import ChatHistoryOut, ChatMessageOut, ChatRequest
from app.services.chat_session import (
    cleanup_old_sessions,
    extract_visitor_name,
    get_or_create_session,
    load_context_messages,
    save_message,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    ip = client_ip(request)
    if not check_rate_limit(ip):
        raise AppError("rate_limited", "Слишком много сообщений, подождите минуту", 429)

    master = (
        await session.execute(select(MasterCV).where(MasterCV.id == 1))
    ).scalar_one_or_none()
    if not master:
        raise AppError("not_found", "Мастер-CV не найден", 404)

    # Получаем или создаём сессию чата
    chat_session = await get_or_create_session(
        session, req.session_id, ip, req.short_link_code
    )

    # Сохраняем user-сообщение
    await save_message(session, chat_session, "user", req.message)

    # Извлекаем имя/email если HR назвался (regex)
    name = extract_visitor_name(req.message)
    if name and not chat_session.visitor_name:
        chat_session.visitor_name = name

    # Загружаем контекст диалога (последние N сообщений)
    context = await load_context_messages(session, chat_session)

    # Lazy cleanup старых сессий (раз в запрос, дёшево)
    await cleanup_old_sessions(session)
    await session.commit()

    # Системный промпт + контекст диалога
    system = await build_system_prompt(session, master.full_markdown)

    async def gen():
        full_response = ""
        try:
            async for token in stream_chat(context, system):
                full_response += token
                yield token
        except Exception:
            logger.exception("z.ai streaming failed")
            fallback = f"\n\n[AI временно недоступен. Свяжитесь напрямую: {settings.contacts_fallback}]"
            full_response += fallback
            yield fallback

        # Сохраняем ответ ассистента в БД
        if full_response.strip():
            await save_message(session, chat_session, "assistant", full_response.strip())
            await session.commit()

    # Устанавливаем cookie с session_id (httpOnly, 24h)
    response = StreamingResponse(gen(), media_type="text/plain")
    response.set_cookie(
        key="cv_session_id",
        value=str(chat_session.id),
        httponly=True,
        max_age=86400,  # 24 часа
        samesite="lax",
    )
    return response


@router.get("/api/chat/history/{session_id}")
async def chat_history(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> ChatHistoryOut:
    """Публичный endpoint: возвращает историю сообщений сессии.

    Фронтенд вызывает при открытии чата, если есть session_id в cookie.
    """
    import uuid as uuid_mod

    try:
        sid = uuid_mod.UUID(session_id)
    except ValueError:
        raise AppError("not_found", "Сессия не найдена", 404)

    chat_session = (
        await session.execute(select(ChatSession).where(ChatSession.id == sid))
    ).scalar_one_or_none()
    if not chat_session:
        raise AppError("not_found", "Сессия не найдена", 404)

    msgs = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sid)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()

    return ChatHistoryOut(
        session_id=str(sid),
        messages=[
            ChatMessageOut(role=m.role, content=m.content, created_at=m.created_at.isoformat())
            for m in msgs
        ],
    )
