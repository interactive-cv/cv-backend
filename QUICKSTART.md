# Quick Start

Полное руководство: локальная разработка → production-деплой → настройка.

---

## Содержание

- [Требования](#требования)
- [Локальная разработка (5 минут)](#локальная-разработка-5-минут)
- [Production-деплой на VPS](#production-деплой-на-vps)
- [Конфигурация: все переменные](#конфигурация-все-переменные)
- [Промпты: настройка и защита от дрифта](#промпты-настройка-и-защита-от-дрифта)
- [Обновление до новой версии](#обновление-до-новой-версии)
- [Тестирование](#тестирование)

---

## Требования

- **Python 3.12+**
- **Node.js 22+**
- **PostgreSQL 16+** (для prod/dev) или SQLite (для тестов — встроен)
- **Docker + Docker Compose** (для production-деплоя)
- **API-ключ z.ai** — для AI-функций (чат, генерация откликов). Получить на [z.ai](https://z.ai).

---

## Локальная разработка (5 минут)

### Backend

```bash
cd cv-backend

# Виртуальное окружение
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Конфигурация
cp .env.example .env
# Отредактируйте .env — минимум: DATABASE_URL, ADMIN_TOKEN, SECRET_KEY, IP_HASH_SECRET, ZAI_API_KEY
# (см. подробности в разделе «Конфигурация» ниже)

# Контент (мастер-CV, проекты, README) — скопируйте примеры:
cp seed_data/master_cv.example.md seed_data/master_cv.md
cp seed_data/projects.example.json seed_data/projects.json
# Отредактируйте под своё CV!

# Миграции + seed
alembic upgrade head
python -m app.seed

# Запуск
uvicorn app.main:app --reload --port 8000
```

Проверка: `curl http://localhost:8000/api/health` → `{"status":"ok"}`

### Frontend

```bash
cd cv-frontend

npm install

# Конфигурация
cp .env.example .env.local
# Отредактируйте .env.local (имя, роль, API URL)

npm run dev
```

Сайт откроется на `http://localhost:3000`.

---

## Production-деплой на VPS

### Предусловия

1. **VPS** с публичным IP, Docker + Docker Compose установлены.
2. **Домен** направлен (A-запись) на IP сервера.
3. Порты 80/443 открыты в файрволе.

### Шаг 1. Внешняя Docker-сеть

edge-прокси (TCP stream-preread) и контейнеры сайта общаются через внешнюю сеть.
Создаётся один раз:

```bash
docker network create libera
```

> Если вы используете собственный edge-прокси (Traefik, Caddy и т.п.) — сеть
> не нужна; адаптируйте `docker-compose.prod.yml` под свой роутинг.

### Шаг 2. Код и конфигурация

```bash
git clone https://github.com/interactive-cv/cv-backend.git
git clone https://github.com/interactive-cv/cv-frontend.git
cd cv-backend

cp .env.example .env
```

Сгенерируйте секреты и заполните `.env`:

```bash
openssl rand -hex 32   # → POSTGRES_PASSWORD, ADMIN_TOKEN, SECRET_KEY, IP_HASH_SECRET
```

Минимум для заполнения:
- `POSTGRES_PASSWORD` — пароль БД (также в `DATABASE_URL`)
- `ADMIN_TOKEN` — bearer-токен для доступа к админке
- `SECRET_KEY`, `IP_HASH_SECRET` — случайные значения
- `SITE_URL` — ваш публичный домен (`https://your-domain.com`)
- `ALLOWED_ORIGINS` — ваш домен (`https://your-domain.com`)
- `ZAI_API_KEY` — ключ z.ai для AI-функций

### Шаг 3. Контент (seed_data)

```bash
cp seed_data/master_cv.example.md seed_data/master_cv.md
cp seed_data/projects.example.json seed_data/projects.json
# Отредактируйте под своё CV!
```

### Шаг 4. TLS-сертификаты (Let's Encrypt)

```bash
mkdir -p /var/www/certbot
certbot certonly --webroot -w /var/www/certbot \
  -d your-domain.com \
  --email your@email.com --agree-tos --no-eff-email
```

Укажите пути к сертификатам в `.env` (см. комментарии в `.env.example`).

### Шаг 5. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Поднимутся: nginx (TLS) → postgres + fastapi + nextjs.

### Шаг 6. Миграции и seed

```bash
docker compose -f docker-compose.prod.yml exec -T fastapi alembic upgrade head
docker compose -f docker-compose.prod.yml exec -T fastapi python -m app.seed
```

### Шаг 7. Smoke-проверки

```bash
curl -s https://your-domain.com/api/health           # → {"status":"ok"}
curl -s https://your-domain.com/api/projects | head -c 80   # → JSON с проектами
curl -s https://your-domain.com/ | grep -o "Your Name"     # → SSR отрендерил
```

### Чеклист перед запуском

- [ ] Все секреты в `.env` сгенерированы (не `changeme`)
- [ ] `SITE_URL` и `ALLOWED_ORIGINS` указывают на ваш домен
- [ ] TLS-сертификаты получены, https работает
- [ ] `seed_data/master_cv.md` и `projects.json` отредактированы под ваше CV
- [ ] `alembic upgrade head` + seed выполнены
- [ ] Smoke-проверки зелёные
- [ ] `ZAI_API_KEY` — реальный ключ (иначе чат отдаёт fallback-сообщение)

---

## Конфигурация: все переменные

### Backend (`.env`)

| Переменная | Обязательная | Описание |
|---|---|---|
| `DATABASE_URL` | ✅ | SQLAlchemy URL (`postgresql+psycopg://user:pass@host:5432/db`) |
| `POSTGRES_PASSWORD` | ✅ | Пароль БД (должен совпадать с `DATABASE_URL`) |
| `ADMIN_TOKEN` | ✅ | Bearer-токен для `/api/admin/*` |
| `SECRET_KEY` | ✅ | Случайная строка (подпись cookies и т.д.) |
| `IP_HASH_SECRET` | ✅ | Соль для хэширования IP посетителей |
| `SITE_URL` | ✅ | Публичный домен (`https://your-domain.com`). От него строятся короткие ссылки. |
| `ALLOWED_ORIGINS` | ✅ | CORS origins (через запятую) |
| `ZAI_API_KEY` | ✅ | Ключ z.ai для AI-функций |
| `ZAI_API_BASE` | по умолч. | `https://api.z.ai/api/coding/paas/v4` (coding-эндпоинт!) |
| `ZAI_MODEL` | по умолч. | `glm-5.2` |
| `CHAT_RATE_PER_HOUR` | по умолч. | `50` — лимит сообщений чата на IP в час |
| `CHAT_RATE_PER_DAY` | по умолч. | `300` — лимит сообщений чата на IP в день |
| `ARTIFACT_MAX_SIZE_MB` | по умолч. | `100` — макс. размер загружаемого артефакта (APK и др.) |
| `CONTACTS_FALLBACK` | опц. | Контакты на случай пустой БД (`email@example.com · Telegram @handle`) |

> **ВАЖНО (z.ai):** подписка GLM Coding Plan работает **только** через coding-эндпоинт
> `https://api.z.ai/api/coding/paas/v4` (НЕ стандартный `/api/paas/v4`).

### Frontend (`.env.local`)

| Переменная | Обязательная | Описание |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | URL backend API (`https://your-domain.com` в prod) |
| `NEXT_PUBLIC_SITE_URL` | ✅ | URL frontend (для OG-метаданных) |
| `NEXT_PUBLIC_OWNER_NAME` | ✅ | Ваше имя (заголовок сайта) |
| `NEXT_PUBLIC_OWNER_ROLE` | ✅ | Роль/специализация (подзаголовок) |
| `NEXT_PUBLIC_OWNER_TAGS` | опц. | Бейджи через запятую (`Flutter,Python,DevOps`) |

### nginx/TLS (в `.env`, для docker-compose)

| Переменная | Описание |
|---|---|
| `LE_EMAIL` | Email для Let's Encrypt |
| `LE_FQDN` | Домен сертификата (`your-domain.com`) |
| `SSL_CERT` / `SSL_KEY` / `SSL_CHAIN_CERT` | Пути к сертификатам |

---

## Промпты: настройка и защита от дрифта

Проект содержит 5 редактируемых промптов в БД (`config_text`):

| Ключ | Назначение |
|---|---|
| `prompt_chat` | Системный промпт HR-чата |
| `prompt_generate` | Генерация отклика на вакансию |
| `prompt_generate_freelance` | Генерация отклика на фриланс-заказ |
| `prompt_generate_contest` | Генерация отклика на конкурс |
| `prompt_cv_edit` | AI-правка мастер-CV по инструкции |

### Как это работает

- При первом запуске (`python -m app.seed`) промпты создаются из дефолтов в `app/seed_defaults.py`.
- **После первого запуска промпты живут в БД** и редактируются через `/admin/settings` (без деплоя).
- `seed_defaults.py` — дефолт **только для fresh install**. Он НЕ перезаписывает промпты при повторных seed.

### Защита от дрифта

При обновлении `seed_defaults.py` (новые правила, новый тон) — промпты на проде **не меняются автоматически**.
Ваши ручные правки (estimate-блоки, кастомный тон) защищены.

Проверка расхождений:

```bash
# Локально (dev БД):
python scripts/check_prompt_drift.py

# Прод (через API):
CV_API_URL=https://your-domain.com CV_ADMIN_TOKEN=xxx python scripts/check_prompt_drift.py

# С полным diff:
python scripts/check_prompt_drift.py --diff
```

Если есть расхождения:
- ✅ **идентичен дефолту** — дрифта нет
- ⚠️ **расхождение** — прод содержит правки или код обновлён

При расхождении — **вы решаете**: применить новые правила через `/admin/settings`, оставить как есть,
или объединить.

---

## Обновление до новой версии

### Через GitHub Actions (рекомендуется)

Проект настроен на автодеплой при merge PR в `master`:

1. Создайте feature-ветку → внесите изменения → push.
2. CI прогоняет тесты (ruff + pytest + build).
3. Откройте PR → merge в `master`.
4. `deploy.yml` автоматически: rsync кода на VPS → rebuild контейнеров → миграции → seed → smoke.

Требуются GitHub Secrets: `DEPLOY_SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`.
См. `.github/workflows/deploy.yml`.

### Вручную (emergency / fallback)

```bash
cd cv-backend
SSH_KEY=~/.ssh/your_key HOST=deploy@your-vps-ip bash deploy.sh
```

`deploy.sh` делает rsync + rebuild + миграции + seed. `.env` на сервере **не перезаписывается**.

---

## Тестирование

### Backend

```bash
cd cv-backend
source .venv/bin/activate

pytest                    # unit-тесты (in-memory SQLite, без внешних зависимостей)
pytest -m e2e             # e2e против реальной LLM (нужен ZAI_API_KEY)
ruff check app/ tests/    # lint
mypy app/                 # типы (опционально)
```

### Frontend

```bash
cd cv-frontend
npm test                  # Jest
npx tsc --noEmit          # type-check
npm run build             # production build
```

---

## Docker Compose: dev vs prod

| Файл | Назначение | Что включает |
|---|---|---|
| `docker-compose.yml` | Локальная dev-разработка | postgres + fastapi (без nginx, без frontend) |
| `docker-compose.prod.yml` | Production | nginx (TLS) + postgres + fastapi + nextjs + volumes |

Dev-compose удобен для быстрого поднятия БД без установки PostgreSQL локально.

---

## Структура проекта

```
cv-backend/
├── app/
│   ├── models/       SQLAlchemy-модели
│   ├── schemas/      Pydantic DTO
│   ├── routers/      эндпоинты (cv, projects, links, chat, admin, downloads)
│   ├── services/     бизнес-логика (резолв ссылок, парсер CV, PDF, чат-сессии)
│   ├── llm/          промпт-инжиниринг и стриминговый клиент
│   └── config.py     настройки из .env
├── alembic/          миграции БД
├── seed_data/        контент (мастер-CV, проекты) — .example файлы для старта
├── seed_defaults.py  дефолтные промпты (fresh install only — см. раздел «Промпты»)
├── scripts/          утилиты (check_prompt_drift.py)
├── tests/            unit + e2e
├── nginx_ssl/        nginx-конфиги и Dockerfile для TLS
├── docker-compose.prod.yml
├── Dockerfile
├── .env.example      шаблон конфигурации
└── QUICKSTART.md     этот файл
```
