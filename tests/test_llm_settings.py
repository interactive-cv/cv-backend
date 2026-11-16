"""Тесты настроек LLM (GET/PATCH /api/admin/llm-settings).

Хранение — таблица app_setting; значения применяются ко всем вызовам
stream_chat (проверка payload — через respx-мок z.ai и подмену
async_session на тестовую in-memory SQLite).
"""
import json

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base
from app.llm.settings import (
    ALLOWED_LLM_MODELS,
    ALLOWED_REASONING_EFFORTS,
    DEFAULT_REASONING_EFFORT,
    LLM_MODEL_KEY,
    LLM_REASONING_KEY,
)

VALID = {"Authorization": f"Bearer {settings.admin_token}"}


@pytest.mark.asyncio
async def test_llm_settings_unauthorized(client):
    res = await client.get("/api/admin/llm-settings")
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_llm_settings_get_defaults(client):
    """Без записей в app_setting — дефолты: env-модель + дефолтный effort."""
    res = await client.get("/api/admin/llm-settings", headers=VALID)
    assert res.status_code == 200
    body = res.json()
    assert body["model"] == settings.zai_model
    assert body["reasoning_effort"] == DEFAULT_REASONING_EFFORT
    assert body["available_models"] == ALLOWED_LLM_MODELS
    assert body["available_reasoning_efforts"] == ALLOWED_REASONING_EFFORTS


@pytest.mark.asyncio
async def test_llm_settings_patch_roundtrip(client):
    """PATCH сохраняет в app_setting; GET возвращает сохранённое."""
    res = await client.patch(
        "/api/admin/llm-settings",
        headers=VALID,
        json={"model": "glm-5.3-flash", "reasoning_effort": "low"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["model"] == "glm-5.3-flash"
    assert body["reasoning_effort"] == "low"

    # Повторный GET читает то же самое (значение сохранилось в БД).
    res2 = await client.get("/api/admin/llm-settings", headers=VALID)
    assert res2.json()["model"] == "glm-5.3-flash"
    assert res2.json()["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_llm_settings_patch_invalid_model(client):
    res = await client.patch(
        "/api/admin/llm-settings",
        headers=VALID,
        json={"model": "gpt-99"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_model"


@pytest.mark.asyncio
async def test_llm_settings_patch_invalid_effort(client):
    res = await client.patch(
        "/api/admin/llm-settings",
        headers=VALID,
        json={"reasoning_effort": "extreme"},
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_reasoning_effort"


@pytest.mark.asyncio
@respx.mock
async def test_stream_chat_uses_saved_model_and_effort(monkeypatch):
    """stream_chat отправляет в z.ai модель и reasoning_effort из app_setting.

    deps.async_session (используется get_effective_llm_settings) подменяется
    на тестовую in-memory SQLite с заранее сохранёнными настройками.
    """
    import app.llm.settings as llm_settings_module
    from app.llm.client import stream_chat
    from app.models import AppSetting

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        s.add(AppSetting(key=LLM_MODEL_KEY, value="glm-5.3-flash"))
        s.add(AppSetting(key=LLM_REASONING_KEY, value="low"))
        await s.commit()

    monkeypatch.setattr(llm_settings_module, "async_session", maker)

    captured: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read()
        sse = (
            'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=sse)

    route = respx.post(f"{settings.zai_api_base}/chat/completions").mock(side_effect=capture)

    chunks = [c async for c in stream_chat([{"role": "user", "content": "привет"}], "sys")]
    assert route.called
    assert "".join(chunks) == "ok"

    body = json.loads(captured["payload"])
    assert body["model"] == "glm-5.3-flash"
    assert body["reasoning_effort"] == "low"

    await engine.dispose()
