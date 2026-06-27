import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session, require_admin
from app.errors import AppError
from app.models import CVVariant, CVVariantStatus, ShortLink
from app.schemas.cv import CVVariantCreateIn
from app.schemas.link import LinkCreateIn

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.post("/variants", status_code=201)
async def create_variant(
    body: CVVariantCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    existing = (
        await session.execute(select(CVVariant).where(CVVariant.slug == body.slug))
    ).scalar_one_or_none()
    if existing:
        raise AppError("conflict", "Slug уже занят", 409)
    v = CVVariant(
        master_cv_id=1,
        slug=body.slug,
        title=body.title,
        company=body.company,
        content_markdown=body.content_markdown,
        vacancy_text=body.vacancy_text,
        status=CVVariantStatus(body.status),
    )
    session.add(v)
    await session.commit()
    return {"slug": v.slug, "id": str(v.id)}


@router.post("/links", status_code=201)
async def create_link(
    body: LinkCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    v = (
        await session.execute(select(CVVariant).where(CVVariant.slug == body.cv_variant_slug))
    ).scalar_one_or_none()
    if not v:
        raise AppError("not_found", "Вариант CV не найден", 404)
    code = secrets.token_hex(3).upper()[:5]  # 5 символов, верхний регистр
    link = ShortLink(
        code=code,
        cv_variant_id=v.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=body.ttl_days),
        max_hits=body.max_hits,
    )
    session.add(link)
    await session.commit()
    return {"code": code, "url": f"https://cv.libera.pro/{code}"}
