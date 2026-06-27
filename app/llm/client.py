import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings


async def stream_chat(messages: list[dict], system: str) -> AsyncIterator[str]:
    """Стримит токены ответа от z.ai (OpenAI-совместимый SSE-протокол).

    messages: список {role, content} — история диалога (без system).
    system: system-prompt с CV-контекстом.
    Поднимает исключение при ошибке API — вызывающий решает, как деградировать.
    """
    headers = {"Authorization": f"Bearer {settings.zai_api_key}"}
    payload = {
        "model": settings.zai_model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
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
