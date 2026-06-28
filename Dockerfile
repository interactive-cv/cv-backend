# Multi-stage: build deps отдельно (кэш), рантайм — минимальный.
# Базовый образ python:3.12 (НЕ slim) — предустановленный setuptools избегает
# нестабильных сетевых скачиваний при uv/pip install (SSL-обрывы в контейнере).
FROM python:3.12 AS base
WORKDIR /app

# Кэшируемый слой зависимостей: ставим uv и зависимости ПЕРЕД копированием кода.
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py
RUN uv pip install --system .

# Копируем остальной код.
COPY . .

EXPOSE 8000
# Прод: без --reload. healthcheck через /api/health.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').read()" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
