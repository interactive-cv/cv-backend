"""Живой журнал обращений к LLM (Z.ai) — для виджета в админке.

Кольцевой буфер в памяти процесса (uvicorn в один воркер): последние N
вызовов с фактическими параметрами запроса — модель, уровень «думания»
(reasoning_effort как он реально уходит в API), источник (эндпоинт),
статус и длительность. Тела запросов/ответов НЕ пишутся.

Переживает в рамках жизни процесса; при рестарте контейнера очищается —
для наблюдения «здесь и сейчас» этого достаточно.
"""
import threading
import time
import uuid
from collections import deque

_MAX_CALLS = 50

_lock = threading.Lock()
_calls: deque[dict] = deque(maxlen=_MAX_CALLS)


def log_start(source: str, model: str, effort: str, temperature: float) -> str:
    """Начало обращения к API: вернуть id события (дописывается в log_finish)."""
    call_id = uuid.uuid4().hex[:8]
    with _lock:
        _calls.appendleft({
            "id": call_id,
            "source": source,
            "model": model,
            "effort": effort,
            "temperature": temperature,
            "started_at": time.time(),
            "status": "running",
            "duration_s": None,
        })
    return call_id


def log_finish(call_id: str, ok: bool, error: str | None = None) -> None:
    """Завершение обращения (успех/ошибка) — дописать статус и длительность."""
    with _lock:
        for c in _calls:
            if c["id"] == call_id:
                c["status"] = "ok" if ok else "error"
                c["duration_s"] = round(time.time() - c["started_at"], 1)
                if error:
                    # только тип/краткая суть, без деталей запроса
                    c["error"] = error[:120]
                break


def recent_calls() -> list[dict]:
    """Снимок журнала (новые сверху) для админ-эндпоинта."""
    with _lock:
        return [dict(c) for c in _calls]
