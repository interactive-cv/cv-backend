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

SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"


def main() -> None:
    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        # --- master_cv (одна строка, id=1) ---
        md = (SEED_DIR / "master_cv.md").read_text(encoding="utf-8")
        existing = session.get(MasterCV, 1)
        if existing:
            existing.full_markdown = md
            existing.version += 1
        else:
            session.add(MasterCV(id=1, summary="", contacts={}, full_markdown=md, version=1))

        # --- projects (полная перезаливка, порядок по файлу) ---
        for p in session.execute(select(Project)).scalars().all():
            session.delete(p)
        data = json.loads((SEED_DIR / "projects.json").read_text(encoding="utf-8"))
        for i, p in enumerate(data):
            session.add(Project(**p, order_idx=i))

        session.commit()

    engine.dispose()
    print(f"seeded OK: master_cv updated, {len(data)} projects inserted")


if __name__ == "__main__":
    main()
