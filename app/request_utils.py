"""Утилиты для работы с HTTP-запросом.

⚠️ КОНТРАКТ: доверие X-Forwarded-For предполагает, что перед FastAPI стоит
trusted-proxy (nginx в Задаче 12), который корректно выставляет этот заголовок.
Если FastAPI когда-либо будет экспонирован напрямую (без доверенного прокси),
клиент сможет подделать XFF и обойти rate-limit. См. nginx.conf (Задача 12).
"""
from fastapi import Request

_TRUSTED_PROXY_HEADERS = ("x-forwarded-for", "x-real-ip")


def client_ip(request: Request) -> str:
    """Реальный IP клиента: из X-Forwarded-For (первый hop) с fallback на client.host."""
    for header in _TRUSTED_PROXY_HEADERS:
        value = request.headers.get(header)
        if value:
            # X-Forwarded-For: "client, proxy1, proxy2" — берём первый (исходный клиент)
            return value.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"
