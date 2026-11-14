# ===== Seed: first-run only для master_cv/projects (деплой не откатывает данные) =====

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import MasterCV, Project
from app.seed import _seed_master_cv, _seed_projects


@pytest.fixture()
def sync_db(monkeypatch, tmp_path):
    """Изолированная sqlite-БД + подменённый SEED_DIR с тестовыми файлами."""
    from app import seed as seed_mod

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    seed_dir = tmp_path / "seed_data"
    seed_dir.mkdir()
    (seed_dir / "master_cv.md").write_text(
        "# Тест CV\n## Контакты\n- **Email**: t@t.ru\n", encoding="utf-8"
    )
    (seed_dir / "projects.json").write_text(
        json.dumps([{"title": "П1", "role": "r", "short_desc": "d",
                     "stack": [], "tags": [], "period": "p", "metrics": {},
                     "links": []}], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_mod, "SEED_DIR", seed_dir)
    with Session(engine) as s:
        yield s
    engine.dispose()


def test_seed_first_run_inserts(sync_db):
    s = sync_db
    assert "inserted (first run)" in _seed_master_cv(s, refresh=False)
    assert "1 projects inserted" in _seed_projects(s, refresh=False)
    s.commit()
    assert s.get(MasterCV, 1).full_markdown.startswith("# Тест CV")
    assert len(s.execute(select(Project)).scalars().all()) == 1


def test_seed_skips_existing_without_refresh(sync_db):
    """Данные есть и refresh=False → seed НЕ перезаписывает (прод-деплой)."""
    s = sync_db
    _seed_master_cv(s, refresh=False)
    _seed_projects(s, refresh=False)
    s.commit()

    # «правка через админку»
    s.get(MasterCV, 1).full_markdown = "# Изменённый CV"
    s.execute(select(Project)).scalars().all()[0].title = "Переименованный"
    s.commit()

    assert "skipped" in _seed_master_cv(s, refresh=False)
    assert "skipped" in _seed_projects(s, refresh=False)
    s.commit()
    assert s.get(MasterCV, 1).full_markdown == "# Изменённый CV"
    assert s.execute(select(Project)).scalars().all()[0].title == "Переименованный"


def test_seed_refresh_overwrites(sync_db):
    """SEED_REFRESH=1 — дев-режим перезаливки из файлов."""
    s = sync_db
    _seed_master_cv(s, refresh=False)
    _seed_projects(s, refresh=False)
    s.commit()
    s.get(MasterCV, 1).full_markdown = "# Правка вручную"
    s.commit()

    assert "refreshed" in _seed_master_cv(s, refresh=True)
    assert "1 projects inserted" in _seed_projects(s, refresh=True)
    s.commit()
    assert s.get(MasterCV, 1).full_markdown.startswith("# Тест CV")
