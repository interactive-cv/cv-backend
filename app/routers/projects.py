from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.models import Project
from app.schemas.project import ProjectOut

router = APIRouter()


@router.get("/api/projects", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectOut]:
    rows = (await session.execute(select(Project).order_by(Project.order_idx))).scalars().all()
    return [
        ProjectOut(
            title=p.title,
            period=p.period,
            role=p.role,
            tags=p.tags,
            short_desc=p.short_desc,
            stack=p.stack,
            metrics=p.metrics,
            order_idx=p.order_idx,
        )
        for p in rows
    ]
