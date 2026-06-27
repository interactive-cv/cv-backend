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
from app.models import MasterCV
from app.ratelimit import check_rate_limit
from app.request_utils import client_ip
from app.schemas.chat import ChatRequest

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

    system = build_system_prompt(master.full_markdown)
    messages = [{"role": "user", "content": req.message}]

    async def gen():
        # Graceful degradation: при падении z.ai отдаём fallback-сообщение,
        # а не 500 — лендинг/граф/CV остаются рабочими (§9 принцип).
        try:
            async for token in stream_chat(messages, system):
                yield token
        except Exception:
            logger.exception("z.ai streaming failed")
            yield f"\n\n[AI временно недоступен. Свяжитесь напрямую: {settings.contacts_fallback}]"

    return StreamingResponse(gen(), media_type="text/plain")
