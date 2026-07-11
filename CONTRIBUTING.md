# Контрибьютинг в interactive-cv

Спасибо за интерес к проекту! Это open-source-шаблон персонального сайта-резюме с AI-ассистентом. Любой может развернуть его под своё CV или контрибьютить код.

## Репозитории

| Репозиторий | Что внутри |
|-------------|-----------|
| [cv-backend](https://github.com/interactive-cv/cv-backend) | Python, FastAPI, PostgreSQL — REST API, AI-промпты, PDF-экспорт |
| [cv-frontend](https://github.com/interactive-cv/cv-frontend) | Next.js 16, TypeScript, Tailwind — SSR-лендинг, граф, чат-виджет, админка |
| [interactive-cv](https://github.com/interactive-cv/interactive-cv) | Org-profile README с описанием проекта |

## Dev-окружение

### Требования

- Python 3.11+
- Node.js 18+ (для фронтенда)
- PostgreSQL 14+ (для прода/dev) или SQLite (для тестов)

### Backend

```bash
cd cv-backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Настройте .env (см. .env.example)
cp .env.example .env
# Отредактируйте: DATABASE_URL, ADMIN_TOKEN, SECRET_KEY, ZAI_API_KEY

# Миграции + seed (мастер-CV, проекты, промпты)
alembic upgrade head
python -m app.seed

# Запуск
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd cv-frontend
npm install

# Настройте .env.local
cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_SITE_URL=http://localhost:3000

npm run dev
```

### Тесты

```bash
# Backend (in-memory SQLite, без внешних зависимостей)
cd cv-backend
pytest                          # unit-тесты (быстро)
pytest -m e2e                   # e2e против реальной LLM (нужен ZAI_API_KEY)

# Frontend
cd cv-frontend
npx tsc --noEmit                # type-check
npm test                        # Jest
```

## Структура проекта

```
cv-backend/
├── app/
│   ├── models/       SQLAlchemy-модели (master_cv, cv_variant, short_link, application, ...)
│   ├── schemas/      Pydantic DTO
│   ├── routers/      эндпоинты (cv, projects, links, chat, admin)
│   ├── services/     бизнес-логика (резолв ссылок, парсер CV, PDF-экспорт)
│   ├── llm/          промпт-инжиниринг и стриминговый клиент
│   └── config.py     настройки из .env
├── alembic/          миграции
├── seed_data/        мастер-CV, проекты, README (контент — не код)
├── tests/            unit + e2e
└── docker-compose.prod.yml
```

## Как контрибьютить

1. **Fork** → создайте ветку: `git checkout -b feature/my-feature`
2. **Пишите тесты** для новой функциональности (pytest для backend, Jest для frontend)
3. **Проверьте** перед PR:
   - Backend: `pytest` (все зелёные), `ruff check app/`, `mypy app/`
   - Frontend: `npx tsc --noEmit`, `npm test`
4. **Commit message** — кратко и по делу: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`
5. **Pull Request** с описанием: что изменилось, зачем, как тестировалось

## Стиль кода

- **Python**: ruff (linting + formatting), mypy (typing). Без `# type: ignore` без причины.
- **TypeScript**: strict mode, без `any`. Functional-стиль, React hooks.
- **Комментарии** — на русском (основной язык проекта), но технические термины — английские (API, endpoint, middleware).

## Идеи для контрибуции

- [ ] Напоминалка о собеседовании (push/email уведомления)
- [ ] Локализация (i18n) админ-панели
- [ ] Темплейты CV (несколько дизайнов)
- [ ] Экспорт в DOCX (помимо PDF)
- [ ] OAuth для админки (вместо bearer-токена)

## Вопросы?

Откройте [Issue](https://github.com/interactive-cv/interactive-cv/issues) — обсудим.

## Лицензия

Контрибьюции лицензируются под [MIT](LICENSE) — так же, как и сам проект.
