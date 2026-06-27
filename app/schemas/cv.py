from typing import Any

from pydantic import BaseModel


class MasterCVOut(BaseModel):
    """Публичный мастер-CV: только открытые поля, без vacancy_text и пр."""

    summary: str
    contacts: dict[str, Any]
    skills_core: dict[str, Any] = {}
    skills_familiar: dict[str, Any] = {}
    languages: dict[str, Any] = {}
    format: dict[str, Any] = {}


class CVVariantOut(BaseModel):
    """Публичный вариант CV. vacancy_text намеренно отсутствует — приватное."""

    slug: str
    title: str
    company: str | None = None
    content_markdown: str


class CVVariantCreateIn(BaseModel):
    """Вход создания варианта CV (admin). vacancy_text допустим тут, не в публичном Out."""

    slug: str
    title: str
    company: str | None = None
    content_markdown: str
    vacancy_text: str | None = None
    status: str = "draft"
