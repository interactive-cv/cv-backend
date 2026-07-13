"""Публичная раздача артефактов конкурсных откликов.

GET /dl/{code} — скачивание файла по короткому коду.
Без admin-auth (как resolve коротких ссылок CV).
Rate limit: check_resolve_rate (защита от перебора кодов).
Если отклик архивирован — 410 Gone.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.errors import AppError
from app.models import ApplicationStatus, Artifact, Application
from app.ratelimit import check_resolve_rate
from app.request_utils import client_ip

router = APIRouter()


@router.get("/dl/{code}")
async def download_artifact(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Скачать артефакт по коду. Публичный доступ."""
    # Rate limit (как у резолва коротких ссылок)
    ip = client_ip(request)
    if not check_resolve_rate(ip):
        raise AppError("rate_limited", "Слишком много запросов", 429)

    # Найти артефакт по коду
    rows = (
        await session.execute(
            select(Artifact, Application)
            .join(Application, Artifact.application_id == Application.id)
            .where(Artifact.code == code.upper())
        )
    ).first()
    if not rows:
        raise AppError("not_found", "Файл не найден", 404)

    artifact, application = rows

    # Архивированный отклик — ссылка мертва
    if application.status == ApplicationStatus.archived:
        raise AppError("gone", "Файл больше недоступен", 410)

    # Атомарный инкремент счётчика скачиваний
    await session.execute(
        update(Artifact)
        .where(Artifact.id == artifact.id)
        .values(download_count=Artifact.download_count + 1)
    )
    await session.commit()

    return FileResponse(
        path=artifact.stored_path,
        media_type=artifact.mime_type or "application/octet-stream",
        filename=artifact.filename,
        content_disposition_type="attachment",
    )
