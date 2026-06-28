import time
from collections import defaultdict, deque

from app.config import settings

# in-memory: (scope, ip) -> deque[timestamp]. Для MVP с одним воркером достаточно.
# Прод-вариант при нескольких воркерах — Redis (см. спека §14 открытые вопросы).
# scope разделяет bucket'ы чата и резолва коротких ссылок.
_buckets: dict[tuple[str, str], deque] = defaultdict(deque)

# Лимит резолва коротких ссылок: защита от брутфорса 5-буквенных кодов (§10).
# Щедрее чата — легитимный HR может открыть несколько ссылок / перешлёт коллегам.
RESOLVE_RATE_PER_HOUR = 20


def _check(ip: str, scope: str, limit: int, window: int = 3600) -> bool:
    """Общий механизм: окно `window` сек, лимит `limit`. True если разрешён."""
    key = (scope, ip)
    now = time.time()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def check_rate_limit(ip: str) -> bool:
    """Чат: двойной лимит (§10) — chat_rate_per_hour И chat_rate_per_day.

    Запрос фиксируется только если прошёл оба лимита.
    """
    # Проверяем оба, но фиксируем только если оба пройдены.
    # Эмулируем peek-then-commit: проверяем, и только при успехе пишем в оба.
    now = time.time()
    hour_key = ("chat_hour", ip)
    day_key = ("chat_day", ip)
    hour = _buckets[hour_key]
    day = _buckets[day_key]
    # вычистка устаревших
    while hour and now - hour[0] > 3600:
        hour.popleft()
    while day and now - day[0] > 86400:
        day.popleft()
    if len(hour) >= settings.chat_rate_per_hour or len(day) >= settings.chat_rate_per_day:
        return False
    hour.append(now)
    day.append(now)
    return True


def check_resolve_rate(ip: str) -> bool:
    """Резолв коротких ссылок: защита от брутфорса кодов (§10). 20/IP/час."""
    return _check(ip, "resolve", RESOLVE_RATE_PER_HOUR)
