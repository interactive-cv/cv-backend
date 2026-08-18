from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_session
from app.errors import AppError
from app.models import ShortLink
from app.ratelimit import check_resolve_rate
from app.request_utils import client_ip
from app.schemas.link import LinkResolveOut
from app.services.chat_session import get_or_create_session
from app.services.links import resolve_link

router = APIRouter()


@router.get("/api/links/resolve", response_model=LinkResolveOut)
async def resolve(
    code: str, request: Request, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    ip = client_ip(request)
    if not check_resolve_rate(ip):
        raise AppError("rate_limited", "Слишком много запросов, подождите минуту", 429)
    ua = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")

    # Проверяем ссылку ДО создания сессии: chat_session.short_link_code
    # имеет FK на short_link.code, вставка с несуществующим кодом даёт
    # FK violation (500) вместо честного 404.
    link = (
        await session.execute(select(ShortLink).where(ShortLink.code == code))
    ).scalar_one_or_none()
    if not link:
        raise AppError("not_found", "Ссылка не найдена", 404)

    # Создаём или находим сессию посетителя (единый профиль: клики + чат).
    cookie_sid = request.cookies.get("cv_session_id")
    chat_session = await get_or_create_session(
        session, cookie_sid, ip, short_link_code=code
    )

    # Если в cookie есть admin-token — помечаем сессию как админскую.
    admin_token = request.cookies.get("cv_admin_token", "")
    if admin_token and admin_token == settings.admin_token:
        chat_session.is_admin = True
        if not chat_session.visitor_name:
            chat_session.visitor_name = "Валерий"

    await session.commit()

    slug, expires_at = await resolve_link(
        code, ip, ua, referrer, session, chat_session_id=chat_session.id
    )

    # Возвращаем JSON + ставим cookie session_id (если новой сессии).
    response = JSONResponse(
        content={"cv_variant_slug": slug, "expires_at": expires_at.isoformat()},
    )
    if not cookie_sid or cookie_sid != str(chat_session.id):
        response.set_cookie(
            key="cv_session_id",
            value=str(chat_session.id),
            httponly=True,
            max_age=86400,
            samesite="lax",
        )
    return response
