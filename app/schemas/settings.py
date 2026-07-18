from datetime import datetime

from pydantic import BaseModel


class ConfigTextOut(BaseModel):
    """Один редактируемый текст (ключ + значение + время обновления)."""

    key: str
    value: str
    updated_at: datetime


class SettingsOut(BaseModel):
    """Все настройки для GET /api/admin/settings."""

    master_cv: ConfigTextOut
    readme: ConfigTextOut
    prompt_chat: ConfigTextOut
    prompt_generate: ConfigTextOut
    prompt_generate_freelance: ConfigTextOut
    prompt_generate_contest: ConfigTextOut
    prompt_cv_edit: ConfigTextOut
    prompt_response_edit: ConfigTextOut


class SettingsUpdateIn(BaseModel):
    """Частичное обновление настроек. Только переданные поля."""

    master_cv: str | None = None
    readme: str | None = None
    prompt_chat: str | None = None
    prompt_generate: str | None = None
    prompt_generate_freelance: str | None = None
    prompt_generate_contest: str | None = None
    prompt_cv_edit: str | None = None
    prompt_response_edit: str | None = None


class CvEditInstructionIn(BaseModel):
    """Вход для AI-правки мастер-CV (предпросмотр)."""

    instruction: str


class CvEditPreviewOut(BaseModel):
    """Результат AI-правки: предпросмотр без сохранения."""

    preview_markdown: str


class CvEditApplyIn(BaseModel):
    """Применение предпросмотра (или ручная правка) к мастер-CV."""

    markdown: str
