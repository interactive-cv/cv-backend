from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.errors import AppError
from app.ratelimit import check_resolve_rate
from app.request_utils import client_ip
from app.schemas.link import LinkResolveOut
from app.services.links import resolve_link

router = APIRouter()


@router.get("/api/links/resolve", response_model=LinkResolveOut)
async def resolve(
    code: str, request: Request, session: AsyncSession = Depends(get_session)
) -> LinkResolveOut:
    ip = client_ip(request)
    # Защита от брутфорса коротких кодов (§10): rate-limit ПЕРЕД обращением к БД.
    if not check_resolve_rate(ip):
        raise AppError("rate_limited", "Слишком много запросов, подождите минуту", 429)
    ua = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    slug, expires_at = await resolve_link(code, ip, ua, referrer, session)
    return LinkResolveOut(cv_variant_slug=slug, expires_at=expires_at)
