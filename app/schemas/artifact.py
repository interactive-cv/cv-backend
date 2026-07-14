"""Pydantic-схемы для артефактов конкурсных откликов."""

from datetime import datetime

from pydantic import BaseModel


class ArtifactOut(BaseModel):
    """Вывод артефакта (для админки)."""

    id: str
    application_id: str
    code: str
    filename: str
    mime_type: str | None = None
    size_bytes: int
    download_count: int
    download_url: str
    created_at: datetime
