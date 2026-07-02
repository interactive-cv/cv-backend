"""Точка входа для запуска бэкенда из IntelliJ IDEA (Run / Debug).

Запускает uvicorn в том же процессе, что и дебаггер IDE — это позволяет
ставить брейкпоинты прямо в коде приложения (app/...) и шагать по нему.

Запуск из IDE:
  - Run configuration "FastAPI Dev" → зелёная стрелка (Ctrl+R)
  - Debug → зелёный жук (Ctrl+D) → брейкпоинты работают

Запуск из терминала (без IDE):
  python dev.py

Запуск с reload (автоперезапуск при изменениях):
  python dev.py --reload

Файл dev.py НЕ зависит от venv-пути: интерпретатор задаётся в Run-конфигурации
(Settings → Project → Python Interpreter → /tmp/cv_venv/bin/python).
"""
import argparse
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev-запуск FastAPI через uvicorn")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Автоперезапуск при изменениях файлов (для разработки)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Хост (по умолчанию 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Порт (по умолчанию 8000)")
    args = parser.parse_args()

    # В debug-режиме IDE reload обычно мешает (перезапуск убивает сессию дебага),
    # но из терминала --reload удобен. Передаём как есть.
    print(f"→ uvicorn app.main:app host={args.host} port={args.port} reload={args.reload}")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    sys.exit(main())
