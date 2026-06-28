# Деплой на VPS (cv.libera.pro)

Пошаговая инструкция для production-деплоя на свой Linux VPS с Docker.

## Предусловия (один раз на сервере)

1. **VPS** с публичным IP, Docker + Docker Compose установлены.
2. **Домены** `cv.libera.pro` и `libera.pro` направлены (A-записи) на IP сервера.
3. Порты 80/443 открыты в файрволе.

## 0. Подготовка кода на сервере

```bash
# Клонируем оба репо рядом (compose ссылается на ../cv-frontend)
cd /opt
git clone <repo-cv-backend> cv-backend
git clone <repo-cv-frontend> cv-frontend
cd cv-backend
```

## 1. Конфигурация окружения

```bash
cp .env.example .env
# ОБЯЗАТЕЛЬНО сгенерировать настоящие секреты (не changeme!):
openssl rand -hex 32   # → POSTGRES_PASSWORD
openssl rand -hex 32   # → ADMIN_TOKEN, SECRET_KEY, IP_HASH_SECRET
nano .env              # вписать значения; ALLOWED_ORIGINS=https://cv.libera.pro
```

Поле `DATABASE_URL` должно совпадать с POSTGRES_USER/PASSWORD/DB.

## 2. TLS-сертификаты (Let's Encrypt)

Сначала получим сертификаты через certbot (до поднятия сервисов, чтобы nginx.conf уже нашёл их):

```bash
# Временно поднимем только nginx для ACME-челленджа, либо используем standalone:
mkdir -p /var/www/certbot
certbot certonly --webroot -w /var/www/certbot \
  -d cv.libera.pro -d libera.pro \
  --email your@email.com --agree-tos --no-eff-email
```

Сертификаты окажутся в `/etc/letsencrypt/live/cv.libera.pro/` и `/etc/letsencrypt/live/libera.pro/`
(nginx.conf уже монтирует этот путь read-only).

## 3. Запуск сервисов

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Это поднимет: nginx (80/443) → postgres + fastapi + nextjs.

## 4. Миграции и seed (первый раз)

```bash
# Применяем схему БД:
docker compose -f docker-compose.prod.yml exec -T fastapi alembic upgrade head
# Наполняем мастер-CV и 16 проектов:
docker compose -f docker-compose.prod.yml exec -T fastapi python -m app.seed
```

## 5. Smoke-проверки

```bash
curl -s https://cv.libera.pro/api/health           # → {"status":"ok"}
curl -s https://cv.libera.pro/api/projects | head -c 80   # → JSON с проектами
curl -sI https://libera.pro                        # → 301 → cv.libera.pro
curl -s https://cv.libera.pro/ | grep -o "Валерий Григорьев"  # → SSR отрендерил
```

## 6. Обновления (ручной деплой с Mac)

Один скрипт `deploy.sh` (в корне cv-backend) — rsync + rebuild + миграции + seed:

```bash
cd /Users/valeriy/ZCodeProject/cv-backend
bash deploy.sh
```

Можно переопределить ключ/хост: `SSH_KEY=~/.ssh/... HOST=deploy@... bash deploy.sh`

⚠️ **Критично:** `deploy.sh` **НЕ перезаписывает** `.env` на VPS (`--exclude='.env'`).
Prod-`.env` содержит реальные секреты (ADMIN_TOKEN, POSTGRES_PASSWORD, z.ai-ключ) и
живёт только на сервере. Меняется вручную на VPS при необходимости:
```bash
ssh deploy@91.132.56.149 'nano /home/deploy/libera_cv/cv-backend/.env'
# после смены секретов — перезапуск: bash deploy.sh или docker compose restart fastapi
```

## 7. Продление сертификатов

Let's Encrypt сертификаты действительны 90 дней. certbot ставит systemd-timer на авто-продление;
после продления нужно перечитать сертификаты в nginx:

```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

(или `crontab`: `0 3 * * * certbot renew --quiet && docker compose ... exec nginx nginx -s reload`)

## Чеклист перед публичным запуском

- [ ] Все секреты в `.env` сгенерированы (не `changeme`)
- [ ] `ADMIN_TOKEN` сложный, нигде не закоммичен
- [ ] TLS-сертификаты получены, https работает
- [ ] `alembic upgrade head` + seed выполнены
- [ ] Smoke-проверки (раздел 5) зелёные
- [ ] Создан хотя бы один cv-вариант (status=active) + короткая ссылка через admin-API
- [ ] `ZAI_API_KEY` — реальный ключ z.ai (иначе чат отдаёт fallback)
