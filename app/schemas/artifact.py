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


class StagedUploadOut(BaseModel):
    """Результат staged-загрузки файла на первом экране нового отклика."""

    id: str
    filename: str
    size_bytes: int
    # Извлечённый текст (pdf/docx/txt) или None, если тип не текстовый
    text: str | None = None
    # Диагноз, если файл сохранён, но текст извлечь не удалось
    error: str | None = None
