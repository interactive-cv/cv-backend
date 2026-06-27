import time
from collections import defaultdict, deque

from app.config import settings

# in-memory: ip -> deque[timestamp]. Для MVP с одним воркером достаточно.
# Прод-вариант при нескольких воркерах — Redis (см. спека §14 открытые вопросы).
_buckets_hour: dict[str, deque] = defaultdict(deque)
_buckets_day: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str) -> bool:
    """True, если запрос разрешён (и фиксирует его); False, если лимит исчерпан.

    Двойной лимит (§10): chat_rate_per_hour (50/IP/час) И chat_rate_per_day (300/IP/день).
    Запрос фиксируется только если прошёл оба лимита.
    """
    now = time.time()
    # --- часовой bucket ---
    hour = _buckets_hour[ip]
    while hour and now - hour[0] > 3600:
        hour.popleft()
    if len(hour) >= settings.chat_rate_per_hour:
        return False
    # --- дневной bucket ---
    day = _buckets_day[ip]
    while day and now - day[0] > 86400:
        day.popleft()
    if len(day) >= settings.chat_rate_per_day:
        return False
    # прошёл оба — фиксируем
    hour.append(now)
    day.append(now)
    return True
