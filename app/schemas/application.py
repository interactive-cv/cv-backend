import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class GenerateIn(BaseModel):
    """Вход AI-генерации CV из вакансии."""

    company: str
    role: str
    vacancy_text: str
    selected_projects: list[str] = []


class GenerateOut(BaseModel):
    """Результат генерации: CV и cover letter (markdown)."""

    cv_markdown: str
    cover_letter_md: str


class ApplicationCreateIn(BaseModel):
    """Создание отклика (после генерации/редактирования)."""

    company: str
    role: str
    vacancy_text: str
    cover_letter_md: str = ""
    cv_markdown: str
    slug: str
    status: Literal["draft", "active"] = "draft"


class ApplicationUpdateIn(BaseModel):
    """Редактирование отклика."""

    cover_letter_md: str | None = None
    cv_markdown: str | None = None
    status: Literal["draft", "active", "archived"] | None = None


class ApplicationOut(BaseModel):
    """Список откликов. vacancy_text НЕ включаем — приватный."""

    id: uuid.UUID
    company: str
    role: str
    slug: str
    status: str
    total_clicks: int = 0
    unique_clicks: int = 0
    short_link_code: str | None = None
    created_at: datetime
    published_at: datetime | None = None


class ApplicationDetailOut(ApplicationOut):
    """Детальный вывод — включает vacancy_text и тексты."""

    vacancy_text: str
    cv_markdown: str = ""
    cover_letter_md: str = ""
    last_click_at: datetime | None = None
