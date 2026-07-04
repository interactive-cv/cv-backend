"""Тесты endpoints /api/admin/settings (Настройки в БД).

Покрывают: GET, PATCH, AI-preview/apply, синхронизацию master_cv.
Не тестируют реальный LLM-вызов (preview с моделью) — он в e2e-маркере.
"""
import pytest

from app.config import settings
from app.models import ConfigText, MasterCV

VALID = {"Authorization": f"Bearer {settings.admin_token}"}


@pytest.mark.asyncio
async def test_get_settings_returns_all_keys(client, session):
    """GET /settings возвращает все 5 ключей."""
    for key in ["master_cv", "readme", "prompt_chat", "prompt_generate", "prompt_cv_edit"]:
        session.add(ConfigText(key=key, value=f"value-{key}"))
    await session.commit()

    res = await client.get("/api/admin/settings", headers=VALID)
    assert res.status_code == 200
    data = res.json()
    for key in ["master_cv", "readme", "prompt_chat", "prompt_generate", "prompt_cv_edit"]:
        assert key in data, f"ключ {key} отсутствует"
        assert data[key]["value"] == f"value-{key}"


@pytest.mark.asyncio
async def test_get_settings_empty_when_no_rows(client, session):
    """GET /settings возвращает пустые значения, если записей нет (fresh install)."""
    res = await client.get("/api/admin/settings", headers=VALID)
    assert res.status_code == 200
    data = res.json()
    for key in ["master_cv", "readme", "prompt_chat", "prompt_generate", "prompt_cv_edit"]:
        assert data[key]["value"] == ""


@pytest.mark.asyncio
async def test_patch_settings_partial_update(client, session):
    """PATCH обновляет только переданные поля."""
    res = await client.patch(
        "/api/admin/settings",
        headers=VALID,
        json={"prompt_chat": "Новый промпт чата"},
    )
    assert res.status_code == 200
    assert res.json()["prompt_chat"]["value"] == "Новый промпт чата"
    # другие поля не затронуты
    assert res.json()["prompt_generate"]["value"] != "Новый промпт чата"


@pytest.mark.asyncio
async def test_patch_settings_unauthorized(client):
    """PATCH без токена → 401."""
    res = await client.patch("/api/admin/settings", json={"prompt_chat": "x"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_patch_master_cv_syncs_master_cv_table(client, session):
    """Сохранение master_cv в config_text синхронно обновляет master_cv.full_markdown."""
    # создаём master_cv строку (нужна для синхронизации)
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# Old", version=1))
    await session.commit()

    new_cv = "# Тестовый Кандидат\n## Summary\nНовый summary для теста."
    res = await client.patch(
        "/api/admin/settings",
        headers=VALID,
        json={"master_cv": new_cv},
    )
    assert res.status_code == 200
    assert res.json()["master_cv"]["value"] == new_cv

    # проверяем, что master_cv таблица обновлена
    master = await session.get(MasterCV, 1)
    assert master.full_markdown == new_cv
    assert "Новый summary" in master.summary
    assert master.version == 2  # инкрементирована


@pytest.mark.asyncio
async def test_apply_master_cv_equivalent_to_patch(client, session):
    """POST /settings/master-cv/apply сохраняет markdown как PATCH {master_cv}."""
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# Old", version=1))
    await session.commit()

    new_md = "# Применённый CV\n## Summary\nЧерез apply endpoint."
    res = await client.post(
        "/api/admin/settings/master-cv/apply",
        headers=VALID,
        json={"markdown": new_md},
    )
    assert res.status_code == 200
    assert res.json()["master_cv"]["value"] == new_md


@pytest.mark.asyncio
async def test_preview_master_cv_requires_existing_cv(client, session):
    """Preview без master_cv в настройках → 404."""
    res = await client.post(
        "/api/admin/settings/master-cv/preview",
        headers=VALID,
        json={"instruction": "Добавь проект X"},
    )
    assert res.status_code == 404
