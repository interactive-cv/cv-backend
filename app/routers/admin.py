import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_session, require_admin
from app.errors import AppError
from app.llm.client import stream_chat
from app.llm.generate_prompt import build_generate_prompt, parse_generate_response
from app.models import (
    Application,
    ApplicationStatus,
    CVVariant,
    CVVariantStatus,
    LinkHit,
    MasterCV,
    ShortLink,
)
from app.schemas.application import (
    ApplicationCreateIn,
    ApplicationDetailOut,
    ApplicationOut,
    ApplicationUpdateIn,
    GenerateIn,
    GenerateOut,
)
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


# ===== Applications (Отклики) =====


async def _count_clicks(session: AsyncSession, code: str | None) -> tuple[int, int]:
    """Возвращает (total_clicks, unique_clicks) для короткой ссылки."""
    if not code:
        return 0, 0
    hits = (
        await session.execute(select(LinkHit).where(LinkHit.short_link_code == code))
    ).scalars().all()
    total = len(hits)
    unique = len({h.ip_hash for h in hits if h.ip_hash})
    return total, unique


@router.post("/applications/generate")
async def generate_cv(
    body: GenerateIn, session: AsyncSession = Depends(get_session)
) -> GenerateOut:
    """AI-генерация адаптированного CV и cover letter из вакансии."""
    master = (
        await session.execute(select(MasterCV).where(MasterCV.id == 1))
    ).scalar_one_or_none()
    if not master:
        raise AppError("not_found", "Мастер-CV не найден", 404)
    prompt = build_generate_prompt(
        master.full_markdown, body.vacancy_text, body.selected_projects
    )
    chunks: list[str] = []
    async for token in stream_chat(
        [{"role": "user", "content": "Сгенерируй отклик"}], prompt
    ):
        chunks.append(token)
    cv_md, cover_md = parse_generate_response("".join(chunks))
    return GenerateOut(cv_markdown=cv_md, cover_letter_md=cover_md)


@router.get("/applications")
async def list_applications(
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationOut]:
    rows = (
        await session.execute(select(Application).order_by(Application.created_at.desc()))
    ).scalars().all()
    result = []
    for a in rows:
        total, unique = await _count_clicks(session, a.short_link_code)
        result.append(
            ApplicationOut(
                id=a.id,
                company=a.company,
                role=a.role,
                slug=a.slug,
                status=a.status.value,
                total_clicks=total,
                unique_clicks=unique,
                short_link_code=a.short_link_code,
                created_at=a.created_at,
                published_at=a.published_at,
            )
        )
    return result


@router.post("/applications", status_code=201)
async def create_application(
    body: ApplicationCreateIn, session: AsyncSession = Depends(get_session)
) -> dict:
    slug = body.slug.lower()
    existing = (
        await session.execute(select(Application).where(Application.slug == slug))
    ).scalar_one_or_none()
    if existing:
        raise AppError("conflict", "Slug уже занят", 409)
    # создаём cv_variant для отклика
    v = CVVariant(
        master_cv_id=1,
        slug=slug,
        title=body.role,
        company=body.company,
        content_markdown=body.cv_markdown,
        status=(
            CVVariantStatus.active if body.status == "active" else CVVariantStatus.draft
        ),
    )
    session.add(v)
    await session.flush()
    app = Application(
        company=body.company,
        role=body.role,
        vacancy_text=body.vacancy_text,
        cover_letter_md=body.cover_letter_md,
        slug=slug,
        cv_variant_id=v.id,
        status=ApplicationStatus(body.status),
    )
    session.add(app)
    await session.commit()
    return {"id": str(app.id), "slug": app.slug}


@router.get("/applications/{app_id}")
async def get_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> ApplicationDetailOut:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    cv_md = ""
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        cv_md = v.content_markdown if v else ""
    total, unique = await _count_clicks(session, a.short_link_code)
    return ApplicationDetailOut(
        id=a.id,
        company=a.company,
        role=a.role,
        slug=a.slug,
        status=a.status.value,
        vacancy_text=a.vacancy_text,
        cv_markdown=cv_md,
        cover_letter_md=a.cover_letter_md or "",
        total_clicks=total,
        unique_clicks=unique,
        short_link_code=a.short_link_code,
        created_at=a.created_at,
        published_at=a.published_at,
    )


@router.patch("/applications/{app_id}")
async def update_application(
    app_id: str,
    body: ApplicationUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    if body.cover_letter_md is not None:
        a.cover_letter_md = body.cover_letter_md
    if body.cv_markdown is not None and a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.content_markdown = body.cv_markdown
    if body.status:
        a.status = ApplicationStatus(body.status)
    await session.commit()
    return {"id": str(a.id), "status": a.status.value}


@router.post("/applications/{app_id}/publish")
async def publish_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    # генерируем короткую ссылку
    code = _generate_code()
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.status = CVVariantStatus.active
        link = ShortLink(
            code=code,
            cv_variant_id=a.cv_variant_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(link)
        a.short_link_code = code
    a.status = ApplicationStatus.active
    a.published_at = datetime.now(timezone.utc)
    await session.commit()
    return {"id": str(a.id), "code": code, "url": f"{settings.site_url}/{code}"}


@router.post("/applications/{app_id}/archive")
async def archive_application(
    app_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    a = (
        await session.execute(
            select(Application).where(Application.id == uuid.UUID(app_id))
        )
    ).scalar_one_or_none()
    if not a:
        raise AppError("not_found", "Отклик не найден", 404)
    a.status = ApplicationStatus.archived
    if a.cv_variant_id:
        v = await session.get(CVVariant, a.cv_variant_id)
        if v:
            v.status = CVVariantStatus.archived
    await session.commit()
    return {"id": str(a.id), "status": "archived"}
