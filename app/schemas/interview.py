"""Pydantic-схемы для интервью (этапы собеседований)."""

from datetime import datetime

from pydantic import BaseModel


class InterviewCreateIn(BaseModel):
    """Создание интервью (этапа собеседования)."""

    scheduled_at: datetime
    notes_before: str | None = None
    notes_after: str | None = None


class InterviewUpdateIn(BaseModel):
    """Редактирование интервью."""

    scheduled_at: datetime | None = None
    notes_before: str | None = None
    notes_after: str | None = None


class InterviewOut(BaseModel):
    """Вывод интервью."""

    id: str
    application_id: str
    scheduled_at: datetime
    notes_before: str | None = None
    notes_after: str | None = None
    created_at: datetime
    # Денормализованные поля отклика — для дашборда «ближайшие»
    application_role: str | None = None
    application_company: str | None = None
