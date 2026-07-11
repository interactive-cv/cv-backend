import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.interview import InterviewOut


class GenerateIn(BaseModel):
    """Вход AI-генерации CV из вакансии или фриланс-заказа."""

    company: str | None = None
    role: str
    vacancy_text: str
    selected_projects: list[str] = []
    kind: Literal["vacancy", "freelance", "contest"] = "vacancy"
    spec_text: str | None = None
    estimate: str | None = None
    extra_instruction: str | None = None
    temperature: float = 0.8


class GenerateOut(BaseModel):
    """Результат генерации: CV (markdown), cover letter (плейн-текст), оценка, промпт."""

    cv_markdown: str
    cover_letter: str
    estimate: str | None = None
    prompt: str = ""


class ApplicationCreateIn(BaseModel):
    """Создание отклика (после генерации/редактирования)."""

    company: str | None = None
    role: str
    vacancy_text: str
    cover_letter: str = ""
    cv_markdown: str
    slug: str
    status: Literal["draft", "active"] = "draft"
    kind: Literal["vacancy", "freelance", "contest"] = "vacancy"
    source_url: str | None = None
    chat_url: str | None = None
    budget: str | None = None
    applicant_count: int | None = None
    deadline: datetime | None = None
    expected_term: str | None = None
    rating: int | None = None
    spec_text: str | None = None
    estimate: str | None = None
    generated_prompt: str | None = None


class ApplicationUpdateIn(BaseModel):
    """Редактирование отклика."""

    company: str | None = None
    role: str | None = None
    cover_letter: str | None = None
    cv_markdown: str | None = None
    status: Literal["draft", "active", "archived"] | None = None
    kind: Literal["vacancy", "freelance", "contest"] | None = None
    source_url: str | None = None
    chat_url: str | None = None
    budget: str | None = None
    applicant_count: int | None = None
    deadline: datetime | None = None
    expected_term: str | None = None
    rating: int | None = None
    spec_text: str | None = None
    estimate: str | None = None


class ApplicationOut(BaseModel):
    """Список откликов. vacancy_text НЕ включаем — приватный."""

    id: uuid.UUID
    company: str | None
    role: str
    slug: str
    status: str
    kind: str = "vacancy"
    total_clicks: int = 0
    unique_clicks: int = 0
    short_link_code: str | None = None
    source_url: str | None = None
    chat_url: str | None = None
    budget: str | None = None
    applicant_count: int | None = None
    deadline: datetime | None = None
    expected_term: str | None = None
    rating: int | None = None
    created_at: datetime
    published_at: datetime | None = None


class ApplicationDetailOut(ApplicationOut):
    """Детальный вывод — включает vacancy_text и тексты."""

    vacancy_text: str
    cv_markdown: str = ""
    cover_letter: str = ""
    spec_text: str | None = None
    estimate: str | None = None
    generated_prompt: str | None = None
    interviews: list[InterviewOut] = []
    last_click_at: datetime | None = None

