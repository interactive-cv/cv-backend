#!/usr/bin/env bash
# rebuild.sh — атомарный rebuild+миграции libera_cv на проде.
# Вызывается: вручную или из GitHub Actions (detached, лог в /tmp/deploy_ci.log).
set -euo pipefail

LOCK=/tmp/libera_cv_deploy.lock
exec 9>"$LOCK"
flock 9

cd /home/deploy/libera_cv/cv-backend

echo "== down"
docker compose -f docker-compose.prod.yml down --remove-orphans

echo "== up --build --wait"
docker compose -f docker-compose.prod.yml up -d --build --wait

echo "== alembic"
docker compose -f docker-compose.prod.yml exec -T fastapi alembic upgrade head

echo "== seed"
docker compose -f docker-compose.prod.yml exec -T fastapi python -m app.seed

echo "== health check"
running=$(docker compose -f docker-compose.prod.yml ps --status running -q | wc -l)
[ "$running" -ge 4 ] || { echo "❌ running only $running/4 services"; exit 1; }

echo "✅ rebuild OK"
