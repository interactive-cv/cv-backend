import httpx
import pytest
import respx

from app.config import settings
from app.llm.prompts import build_system_prompt
from app.main import create_app  # noqa: F401 — гарантирует, что приложение импортируемо
from app.models import MasterCV


def test_system_prompt_grounds_in_cv_and_forbids_invention():
    cv_md = "# CV\nЯ работаю с Flutter."
    prompt = build_system_prompt(cv_md)
    # CV-контекст встроен
    assert "Flutter" in prompt
    # явный запрет выдумывать
    assert "не выдумывай" in prompt.lower() or "не придумывай" in prompt.lower()
    # принцип «только по фактам из CV» (grounding)
    assert (
        "только по фактам" in prompt.lower()
        or "только по факту" in prompt.lower()
        or "только из" in prompt.lower()
    )


# ---- rate-limiter (unit) ----


def test_rate_limit_allows_until_threshold():
    from app.ratelimit import check_rate_limit

    # каждый тест получает общее in-memory состояние — используем уникальный IP
    ip = "10.99.0.1"
    allowed = sum(1 for _ in range(55) if check_rate_limit(ip))
    # лимит 50/час → ровно 50 разрешений, далее отказ
    assert allowed == 50


# ---- chat endpoint (integration with mocked z.ai) ----


@pytest.fixture
async def master_in_db(session):
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV\nFlutter", version=1))
    await session.commit()


@pytest.mark.asyncio
@respx.mock
async def test_chat_streams_tokens(client, master_in_db):
    sse_body = (
        'data: {"choices":[{"delta":{"content":"Я работаю с "}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"Flutter."}}]}\n\n'
        'data: [DONE]\n\n'
    )
    respx.post(f"{settings.zai_api_base}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse_body)
    )
    resp = await client.post("/api/chat", json={"message": "Чем занимаешься?"})
    assert resp.status_code == 200
    assert "Flutter" in resp.text


@pytest.mark.asyncio
async def test_chat_rate_limited_returns_429(client, master_in_db):
    # предзаполняем bucket на этом IP до лимита (50/час) напрямую,
    # затем эндпоинт должен сразу отдать 429, не трогая z.ai.
    from app.ratelimit import check_rate_limit

    ip = "10.99.0.2"
    while check_rate_limit(ip):
        pass
    resp = await client.post("/api/chat", json={"message": "test"}, headers={"x-forwarded-for": ip})
    assert resp.status_code == 429
    assert resp.json()["error"] == "rate_limited"


@pytest.mark.asyncio
async def test_chat_no_master_cv_returns_404(client):
    # мастер-CV не создан → 404 в едином формате (rate-limit проходит на свежем IP)
    resp = await client.post(
        "/api/chat", json={"message": "test"}, headers={"x-forwarded-for": "10.99.0.4"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


@pytest.mark.asyncio
@respx.mock
async def test_chat_zai_failure_fallback(client, master_in_db):
    # z.ai вернул 500 → graceful degradation, fallback-сообщение, НЕ 500
    respx.post(f"{settings.zai_api_base}/chat/completions").mock(
        return_value=httpx.Response(500, text="upstream error")
    )
    resp = await client.post(
        "/api/chat",
        json={"message": "test"},
        headers={"x-forwarded-for": "10.99.0.3"},
    )
    assert resp.status_code == 200
    assert "недоступен" in resp.text.lower() or "свяжитесь" in resp.text.lower()

