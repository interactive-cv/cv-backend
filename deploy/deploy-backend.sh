#!/usr/bin/env bash
# deploy.sh — деплой бэкенда (fastapi + nginx) на проде.
#
# Вызывается из GitHub Actions (отключённым от ssh процессом) или вручную на VPS.
#
# Порядок шагов рассчитан на то, чтобы сайт не простаивал всё время сборки
# (базовые образы могут качаться из Docker Hub часами):
#   1. build   — образы собираются, пока работают прежние контейнеры;
#   2. migrate — миграции выполняются новым образом во временном контейнере,
#                пока прежний код ещё обслуживает запросы. Поэтому миграции
#                должны быть совместимы со старым кодом (только добавление:
#                новые таблицы, nullable-колонки). Убирать старое можно лишь
#                следующим релизом, после того как старый код перестал работать.
#                Необратимые миграции — только после pg_dump (DEPLOY_RULES.md);
#   3. up      — контейнеры пересоздаются из готовых образов (--no-build);
#                меняются только те, у кого изменился образ или конфигурация;
#   4. seed, проверка здоровья.
#
# Ошибка на шагах 1–2 оставляет прод на прежней версии.
# У docker-команд ввод отключён (< /dev/null): compose run иначе подключает stdin
# и может съесть ввод вызвавшего (скрипт по ssh, конвейер).
# Фронт (nextjs) деплоит отдельный скрипт из репозитория cv-frontend.
set -euo pipefail

APP_DIR="${LIBERA_CV_APP_DIR:-/home/deploy/libera_cv/cv-backend}"
# Блокировка общая с деплоем фронта: на сервере 2 vCPU / 3 ГБ без swap,
# параллельные сборки не выдержат. Ждём ограниченно — процесс, потерявший
# свой ssh-клиент (упавший CI-джоб), не должен ждать вечно и сработать потом.
LOCK="${LIBERA_CV_LOCK:-/tmp/libera_cv_deploy.lock}"
LOCK_WAIT="${DEPLOY_LOCK_WAIT:-1800}"

cd "$APP_DIR"
compose() { docker compose -f docker-compose.prod.yml "$@"; }

exec 9>"$LOCK"
echo "== блокировка деплоя (ждём до $((LOCK_WAIT / 60)) мин)"
flock -w "$LOCK_WAIT" 9 || {
  echo "❌ другой деплой не освободил блокировку за $((LOCK_WAIT / 60)) мин — запустите позже"
  exit 2
}

echo "== build (прод работает на прежних контейнерах)"
compose build fastapi web_nginx

echo "== alembic upgrade (новый образ; прежний код ещё обслуживает запросы)"
compose run --rm --no-deps -T fastapi alembic upgrade head < /dev/null

echo "== up (пересоздание изменившихся контейнеров из готовых образов)"
compose up -d --no-build --wait --remove-orphans fastapi web_nginx < /dev/null

echo "== seed"
compose exec -T fastapi python -m app.seed

echo "== health check"
running=$(compose ps --status running -q | wc -l)
[ "$running" -ge 4 ] || { echo "❌ running only $running/4 services"; exit 1; }

echo "✅ deploy OK"
