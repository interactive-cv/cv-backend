"""Утилиты для работы с HTTP-запросом.

За nginx/прокси реальный IP клиента — в X-Forwarded-For (первый hop),
request.client.host даёт IP прокси, а не клиента.
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
