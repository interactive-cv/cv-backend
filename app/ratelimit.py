import time
from collections import defaultdict, deque

from app.config import settings

# in-memory: ip -> deque[timestamp]. Для MVP с одним воркером достаточно.
# Прод-вариант при нескольких воркерах — Redis (см. спека §14 открытые вопросы).
_buckets: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str) -> bool:
    """True, если запрос разрешён (и фиксирует его); False, если лимит исчерпан.

    Окно — 1 час, лимит из settings.chat_rate_per_hour (§10: 50/IP/час).
    """
    now = time.time()
    bucket = _buckets[ip]
    # вычищаем устаревшие записи (старше часа)
    while bucket and now - bucket[0] > 3600:
        bucket.popleft()
    if len(bucket) >= settings.chat_rate_per_hour:
        return False
    bucket.append(now)
    return True
