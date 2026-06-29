import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_session, require_admin
from app.errors import AppError
from app.models import CVVariant, CVVariantStatus, ShortLink
from app.schemas.cv import CVVariantCreateIn
from app.schemas.link import LinkCreateIn

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

# Алфавит коротких кодов: ТОЛЬКО буквы (без цифр) → гарантия isupper()=True (§4 верхний регистр).
# 26^5 ≈ 11.9M вариантов — достаточно для коротких ссылок и устойчивее к digits-only edge case.
_CODE_ALPHABET = string.ascii_uppercase  # ABCDEFGHIJKLMNOPQRSTUVWXYZ
_CODE_LENGTH = 5
_MAX_CODE_RETRIES = 5


def _generate_code() -> str:
    """Случайный код из 5 заглавных букв (без цифр)."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


@router.post("/variants", status_code=201)
async def create_variant(
    body: CVVariantCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    # §4: slug — нижний регистр, человекочитаемый. Нормализуем.
    slug = body.slug.lower()
    existing = (
        await session.execute(select(CVVariant).where(CVVariant.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise AppError("conflict", "Slug уже занят", 409)
    v = CVVariant(
        master_cv_id=1,
        slug=slug,
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
    # Генерация с retry на случай редкой коллизии (code — PK).
    for _ in range(_MAX_CODE_RETRIES):
        code = _generate_code()
        exists = (
            await session.execute(select(ShortLink).where(ShortLink.code == code))
        ).scalar_one_or_none()
        if not exists:
            break
    else:
        raise AppError("conflict", "Не удалось сгенерировать уникальный код ссылки", 409)
    link = ShortLink(
        code=code,
        cv_variant_id=v.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=body.ttl_days),
        max_hits=body.max_hits,
    )
    session.add(link)
    await session.commit()
    return {"code": code, "url": f"{settings.site_url}/{code}"}
