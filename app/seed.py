"""Seed-скрипт: наполняет master_cv и project из seed_data/.

Запуск (при поднятой БД):
    python -m app.seed

Идемпотентен: master_cv перезаписывается, проекты удаляются и вставляются заново.
"""
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MasterCV, Project
from app.services.cv_parser import parse_master_cv

SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"


def _read_seed(name: str) -> str:
    """Читает seed-файл. Если реального нет — подсказывает скопировать из .example."""
    path = SEED_DIR / name
    if not path.exists():
        example = SEED_DIR / f"{name}.example"
        raise SystemExit(
            f"❌ Файл seed_data/{name} не найден.\n"
            f"   Скопируйте пример и отредактируйте под себя:\n"
            f"     cp {example} {path}\n"
            f"   Затем повторите seed."
        )
    return path.read_text(encoding="utf-8")


def main() -> None:
    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        # --- master_cv (одна строка, id=1) ---
        md = _read_seed("master_cv.md")
        parsed = parse_master_cv(md)
        existing = session.get(MasterCV, 1)
        if existing:
            existing.full_markdown = md
            existing.summary = parsed["summary"]
            existing.contacts = parsed["contacts"]
            existing.skills_core = parsed["skills_core"]
            existing.skills_familiar = parsed["skills_familiar"]
            existing.languages = parsed["languages"]
            existing.format = parsed["format"]
            existing.version += 1
        else:
            session.add(
                MasterCV(
                    id=1,
                    summary=parsed["summary"],
                    contacts=parsed["contacts"],
                    skills_core=parsed["skills_core"],
                    skills_familiar=parsed["skills_familiar"],
                    languages=parsed["languages"],
                    format=parsed["format"],
                    full_markdown=md,
                    version=1,
                )
            )

        # --- projects (полная перезаливка, порядок по файлу) ---
        for p in session.execute(select(Project)).scalars().all():
            session.delete(p)
        data = json.loads(_read_seed("projects.json"))
        for i, p in enumerate(data):
            session.add(Project(**p, order_idx=i))

        session.commit()

    engine.dispose()
    print(f"seeded OK: master_cv updated, {len(data)} projects inserted")


if __name__ == "__main__":
    main()
