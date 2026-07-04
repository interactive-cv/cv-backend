"""Seed-скрипт: наполняет master_cv и project из seed_data/.

Запуск (при поднятой БД):
    python -m app.seed

Идемпотентен:
- master_cv / projects: перезаписываются при каждом запуске.
- config_text (мастер-CV, README, промпты): заполняется ТОЛЬКО при первом
  запуске (если ключей нет). После — правки только через админку (/admin/settings).
"""
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CONFIG_KEYS, ConfigText, MasterCV, Project
from app.seed_defaults import (
    DEFAULT_PROMPT_CHAT,
    DEFAULT_PROMPT_CV_EDIT,
    DEFAULT_PROMPT_GENERATE,
    DEFAULT_PROMPT_GENERATE_FREELANCE,
)
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


def _read_seed_optional(name: str) -> str | None:
    """Читает seed-файл если он есть, иначе None (для опциональных файлов)."""
    path = SEED_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else None


def _seed_config_text(session: Session) -> int:
    """Заполняет config_text дефолтами ТОЛЬКО при первом запуске.

    Возвращает количество созданных записей (0 если уже было заполнено).
    """
    existing_count = len(session.execute(select(ConfigText)).scalars().all())
    if existing_count > 0:
        return 0

    defaults: dict[str, str] = {
        "master_cv": _read_seed("master_cv.md"),
        "readme": _read_seed_optional("readme.md") or _read_seed("readme.md.example"),
        "prompt_chat": DEFAULT_PROMPT_CHAT,
        "prompt_generate": DEFAULT_PROMPT_GENERATE,
        "prompt_generate_freelance": DEFAULT_PROMPT_GENERATE_FREELANCE,
        "prompt_cv_edit": DEFAULT_PROMPT_CV_EDIT,
    }
    for key in CONFIG_KEYS:
        session.add(ConfigText(key=key, value=defaults.get(key, "")))
    return len(CONFIG_KEYS)


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

        # --- config_text (только при первом запуске) ---
        config_created = _seed_config_text(session)

        session.commit()

    engine.dispose()
    msg = f"seeded OK: master_cv updated, {len(data)} projects inserted"
    if config_created:
        msg += f", {config_created} config_text rows created (first run)"
    else:
        msg += ", config_text skipped (already filled)"
    print(msg)


if __name__ == "__main__":
    main()
