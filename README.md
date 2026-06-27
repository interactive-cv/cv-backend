# cv-backend

FastAPI + PostgreSQL. Источник правды (спека): `../CV/docs/specs/2026-06-26-libera-phase1-design.md`

## Запуск (dev)

```bash
cp .env.example .env
docker compose up
```

API: http://localhost:8000/api/health → `{"status":"ok"}`

## Тесты

```bash
pip install -e ".[dev]"
pytest
```

## Стек

FastAPI · SQLAlchemy 2.0 + Alembic · PostgreSQL · Pydantic v2 · httpx (z.ai).
Часть проекта «CV» (портфолио Валерия Григорьева) — backend-репо для витрины `cv.libera.pro`.
