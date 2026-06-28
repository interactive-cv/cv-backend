#!/usr/bin/env bash
# Ручной деплой cv.libera.pro с локальной машины (Mac).
# Запуск из cv-backend/:  bash deploy.sh
#
# Что делает:
#   1. rsync'ит cv-backend и cv-frontend на VPS (БЕЗ .env/.venv/node_modules)
#   2. пересобирает образы и перезапускает стек
#   3. прогоняет миграции + seed
#
# ВАЖНО: .env на проде НЕ перезаписывается (содержит реальные секреты).
# Секреты меняются вручную на VPS, если нужно.

set -euo pipefail

# --- конфигурация ---
SSH_KEY="${SSH_KEY:-$HOME/.ssh/libera_cv_2026}"   # ваш рабочий ключ
HOST="${HOST:-deploy@91.132.56.149}"
REMOTE_DIR="/home/deploy/libera_cv"
API_URL="https://cv.libera.pro"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/../cv-frontend" 2>/dev/null && pwd)"

if [ ! -f "$SSH_KEY" ]; then
  echo "❌ SSH-ключ не найден: $SSH_KEY"; echo "   укажите: SSH_KEY=... bash deploy.sh"; exit 1
fi
if [ ! -d "$FRONTEND_DIR" ]; then
  echo "❌ cv-frontend не найден рядом с cv-backend ($FRONTEND_DIR)"; exit 1
fi

SSH_OPTS="-i $SSH_KEY -o ConnectTimeout=15"
RSYNC_SSH="ssh $SSH_OPTS"

echo "=== 1/4 rsync cv-backend (без .env/.venv/.git) ==="
rsync -az --delete \
  --exclude='.env' --exclude='.venv' --exclude='.git' \
  --exclude='__pycache__' --exclude='*.egg-info' \
  --exclude='.pytest_cache' --exclude='.ruff_cache' \
  -e "$RSYNC_SSH" "$BACKEND_DIR/" "$HOST:$REMOTE_DIR/cv-backend/"

echo "=== 2/4 rsync cv-frontend (без node_modules/.next/.git) ==="
rsync -az --delete \
  --exclude='node_modules' --exclude='.next' --exclude='.git' --exclude='.cache' \
  -e "$RSYNC_SSH" "$FRONTEND_DIR/" "$HOST:$REMOTE_DIR/cv-frontend/"

echo "=== 3/4 rebuild + restart (libera_cv) ==="
ssh $SSH_OPTS "$HOST" "cd $REMOTE_DIR/cv-backend && docker compose -f docker-compose.prod.yml up -d --build" 2>&1 | tail -8

echo "=== 4/4 миграции + seed ==="
ssh $SSH_OPTS "$HOST" "cd $REMOTE_DIR/cv-backend && \
  docker compose -f docker-compose.prod.yml exec -T fastapi alembic upgrade head && \
  docker compose -f docker-compose.prod.yml exec -T fastapi python -m app.seed" 2>&1 | tail -3

echo ""
echo "=== smoke: health ==="
curl -s --resolve cv.libera.pro:443:91.132.56.149 "$API_URL/api/health" --max-time 15 && echo
echo "✅ деплой завершён: $API_URL"
