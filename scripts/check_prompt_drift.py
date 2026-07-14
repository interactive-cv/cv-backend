#!/usr/bin/env python3
"""Сравнивает промпты в БД (config_text) с дефолтами в коде (seed_defaults.py).

Цель: защитить ручные правки промптов на проде от случайной перезаписи
при обновлении seed_defaults.py.

Использование:
    # Локально (dev БД из .env):
    python scripts/check_prompt_drift.py

    # Прод (через API):
    CV_API_URL=https://cv.libera.pro CV_ADMIN_TOKEN=xxx python scripts/check_prompt_drift.py

    # Показать полный diff для расходящихся промптов:
    python scripts/check_prompt_drift.py --diff

Правила (см. DEPLOY_RULES.md):
- Изменение seed_defaults.py НЕ перезаписывает промпты на проде автоматически.
- Этот скрипт показывает расхождения; владелец решает — вносить правки руками
  через /admin/settings или осознанно подтверждать per-prompt перезапись.
"""
import argparse
import difflib
import json
import os
import sys
import urllib.request

# Позволяем импорт из app/ при запуске из корня репо
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.seed_defaults import (
    DEFAULT_PROMPT_CHAT,
    DEFAULT_PROMPT_CV_EDIT,
    DEFAULT_PROMPT_GENERATE,
    DEFAULT_PROMPT_GENERATE_CONTEST,
    DEFAULT_PROMPT_GENERATE_FREELANCE,
)

# Маппинг: ключ config_text → (дефолт из кода, человекочитаемое имя)
PROMPTS = {
    "prompt_chat": (DEFAULT_PROMPT_CHAT, "HR-чат"),
    "prompt_generate": (DEFAULT_PROMPT_GENERATE, "Генерация (вакансии)"),
    "prompt_generate_freelance": (DEFAULT_PROMPT_GENERATE_FREELANCE, "Генерация (фриланс)"),
    "prompt_generate_contest": (DEFAULT_PROMPT_GENERATE_CONTEST, "Генерация (конкурс)"),
    "prompt_cv_edit": (DEFAULT_PROMPT_CV_EDIT, "AI-правка CV"),
}


def fetch_prod_prompts(api_url: str, token: str) -> dict[str, str]:
    """Получает промпты с прода через GET /api/admin/settings."""
    req = urllib.request.Request(
        f"{api_url}/api/admin/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return {key: data[key]["value"] for key in PROMPTS}


def fetch_local_prompts() -> dict[str, str]:
    """Получает промпты из локальной БД (через синхронный psycopg)."""
    from app.config import settings
    from psycopg import connect

    # settings.database_url содержит SQLAlchemy-схему "postgresql+psycopg://..."
    # Чистому psycopg нужен "postgresql://..."
    url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM config_text")
            return {row[0]: row[1] for row in cur.fetchall()}


def main():
    parser = argparse.ArgumentParser(description="Сравнение промптов: БД vs код-дефолт")
    parser.add_argument("--diff", action="store_true", help="Показать полный diff для расходящихся")
    args = parser.parse_args()

    api_url = os.environ.get("CV_API_URL")
    token = os.environ.get("CV_ADMIN_TOKEN")

    if api_url and token:
        print(f"Источник: ПРОД ({api_url})\n")
        prod = fetch_prod_prompts(api_url, token)
    else:
        print("Источник: локальная БД (из .env)\n")
        prod = fetch_local_prompts()

    drift_found = False

    for key, (default_val, label) in PROMPTS.items():
        prod_val = prod.get(key, "")

        if not prod_val:
            print(f"  ❓ {label:25} ({key})")
            print("     НЕТ в БД — будет создан из дефолта при первом seed")
            drift_found = True
            continue

        if prod_val == default_val:
            print(f"  ✅ {label:25} ({key})  ≡ идентичен дефолту")
        else:
            delta = len(prod_val) - len(default_val)
            sign = "+" if delta >= 0 else ""
            print(f"  ⚠️  {label:25} ({key})  ≠ РАСХОЖДЕНИЕ (prod={len(prod_val)}, code={len(default_val)}, Δ={sign}{delta})")
            drift_found = True

            if args.diff:
                print()
                diff_lines = list(difflib.unified_diff(
                    default_val.splitlines(keepends=True),
                    prod_val.splitlines(keepends=True),
                    fromfile="code (seed_defaults.py)",
                    tofile="prod (config_text)",
                    n=1,
                ))
                # difflib отдаёт bytes если входы bytes; у нас str
                sys.stdout.writelines(diff_lines)
                print()

    print()
    if drift_found:
        print("ℹ️  Расхождения — не обязательно проблема.")
        print("   Если прод содержит ручные правки владельца — это нормально.")
        print("   Если в коде новый дефолт, который нужно применить — внесите")
        print("   правки через /admin/settings (осознанно, не blindly).")
    else:
        print("✅ Все промпты идентичны дефолтам. Дрифта нет.")


if __name__ == "__main__":
    main()
