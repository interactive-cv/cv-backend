from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.errors import AppError
from app.models import CVVariant, CVVariantStatus, MasterCV
from app.schemas.cv import CVVariantOut, MasterCVOut

router = APIRouter()


@router.get("/api/cv/master", response_model=MasterCVOut)
async def get_master_cv(session: AsyncSession = Depends(get_session)) -> MasterCVOut:
    master = (await session.execute(select(MasterCV).where(MasterCV.id == 1))).scalar_one_or_none()
    if not master:
        raise AppError("not_found", "Мастер-CV не найден", 404)
    return MasterCVOut(
        summary=master.summary,
        contacts=master.contacts,
        skills_core=master.skills_core,
        skills_familiar=master.skills_familiar,
        languages=master.languages,
        format=master.format,
    )


@router.get("/api/variants/{slug}", response_model=CVVariantOut)
async def get_variant(slug: str, session: AsyncSession = Depends(get_session)) -> CVVariantOut:
    v = (
        await session.execute(
            select(CVVariant).where(
                CVVariant.slug == slug, CVVariant.status == CVVariantStatus.active
            )
        )
    ).scalar_one_or_none()
    if not v:
        raise AppError("not_found", "Вариант CV не найден или неактивен", 404)
    return CVVariantOut(
        slug=v.slug, title=v.title, company=v.company, content_markdown=v.content_markdown
    )
