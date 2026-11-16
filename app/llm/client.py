import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.llm.settings import get_effective_llm_settings

logger = logging.getLogger(__name__)


async def stream_chat(
    messages: list[dict],
    system: str,
    temperature: float = 0.8,
) -> AsyncIterator[str]:
    """Стримит токены ответа от z.ai (OpenAI-совместимый SSE-протокол).

    messages: список {role, content} — история диалога (без system).
    system: system-prompt с CV-контекстом.
    temperature: 0.0-1.0. Чат — 0.8 (креативность), генерация CV — 0.3 (стабильность).

    Модель и reasoning_effort берутся из app_setting (переключатель в админке)
    при каждом вызове; если настроек нет — env ZAI_MODEL + дефолт API.
    Поднимает исключение при ошибке API — вызывающий решает, как деградировать.
    """
    headers = {"Authorization": f"Bearer {settings.zai_api_key}"}
    model, reasoning_effort = await get_effective_llm_settings()
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": True,
        "temperature": temperature,
        "reasoning_effort": reasoning_effort,
    }
    async with httpx.AsyncClient(timeout=120) as client, client.stream(
        "POST",
        f"{settings.zai_api_base}/chat/completions",
        headers=headers,
        json=payload,
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                chunk = json.loads(line[6:])
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta
