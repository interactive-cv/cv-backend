import httpx
import pytest
import respx

from app.config import settings
from app.models import MasterCV

VALID = {"Authorization": f"Bearer {settings.admin_token}"}


@pytest.mark.asyncio
async def test_admin_create_variant_unauthorized_no_token(client):
    # без токена → 401 (а не 422), в едином AppError-формате
    res = await client.post(
        "/api/admin/variants", json={"slug": "x", "title": "t", "content_markdown": "# m"}
    )
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_admin_create_variant_unauthorized_wrong_token(client):
    res = await client.post(
        "/api/admin/variants",
        json={"slug": "x", "title": "t", "content_markdown": "# m"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_create_variant_success(client, session):
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    await session.commit()
    res = await client.post(
        "/api/admin/variants",
        headers=VALID,
        json={"slug": "yandex", "title": "Flutter", "content_markdown": "# Yandex CV"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "yandex"
    assert "id" in body


@pytest.mark.asyncio
async def test_admin_create_variant_conflict_on_duplicate_slug(client, session):
    from app.models import CVVariant, CVVariantStatus

    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    session.add(
        CVVariant(
            master_cv_id=1, slug="dup", title="t", content_markdown="# m",
            status=CVVariantStatus.draft,
        )
    )
    await session.commit()
    res = await client.post(
        "/api/admin/variants",
        headers=VALID,
        json={"slug": "dup", "title": "t2", "content_markdown": "# m2"},
    )
    assert res.status_code == 409
    assert res.json()["error"] == "conflict"


@pytest.mark.asyncio
async def test_admin_create_link_success(client, session):
    from app.models import CVVariant, CVVariantStatus

    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    session.add(
        CVVariant(
            master_cv_id=1, slug="sber", title="t", content_markdown="# m",
            status=CVVariantStatus.active,
        )
    )
    await session.commit()
    res = await client.post(
        "/api/admin/links", headers=VALID, json={"cv_variant_slug": "sber", "ttl_days": 14}
    )
    assert res.status_code == 201
    body = res.json()
    assert "code" in body
    assert body["url"].startswith("https://cv.example.com/")
    # код — верхний регистр, 4-6 символов
    assert body["code"].isupper() and 4 <= len(body["code"]) <= 6


@pytest.mark.asyncio
async def test_admin_create_link_unknown_variant_404(client, session):
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    await session.commit()
    res = await client.post(
        "/api/admin/links", headers=VALID, json={"cv_variant_slug": "no-such-variant"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_variant_persists_and_visible_publicly(client, session):
    """Созданный через admin вариант виден через публичный GET /api/variants/{slug}."""
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    await session.commit()
    res = await client.post(
        "/api/admin/variants",
        headers=VALID,
        json={
            "slug": "tinkoff",
            "title": "Tinkoff Flutter",
            "content_markdown": "# T CS",
            "status": "active",
        },
    )
    assert res.status_code == 201
    # публичный эндпоинт находит созданный вариант
    pub = await client.get("/api/variants/tinkoff")
    assert pub.status_code == 200
    assert pub.json()["title"] == "Tinkoff Flutter"


@pytest.mark.asyncio
async def test_admin_create_variant_normalizes_slug_to_lowercase(client, session):
    """§4: slug приводится к нижнему регистру."""
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    await session.commit()
    res = await client.post(
        "/api/admin/variants",
        headers=VALID,
        json={"slug": "YANDEX", "title": "t", "content_markdown": "# m"},
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "yandex"


# ===== Applications (Отклики) =====


@pytest.mark.asyncio
@respx.mock
async def test_admin_generate_cv(client, session):
    from app.models import MasterCV

    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV\nFlutter", version=1))
    await session.commit()
    sse = (
        'data: {"choices":[{"delta":{"content":"===CV===\\n# CV\\n===COVER===\\n# Cover"}}]}\n\n'
        'data: [DONE]\n\n'
    )
    respx.post(f"{settings.zai_api_base}/chat/completions").mock(
        return_value=httpx.Response(200, text=sse)
    )
    res = await client.post(
        "/api/admin/applications/generate",
        headers=VALID,
        json={"company": "Y", "role": "R", "vacancy_text": "Flutter dev", "selected_projects": []},
    )
    assert res.status_code == 200
    data = res.json()
    assert "# CV" in data["cv_markdown"]
    assert "# Cover" in data["cover_letter"]
    assert "prompt" in data
    assert len(data["prompt"]) > 0  # промпт собран и возвращён


@pytest.mark.asyncio
async def test_admin_create_and_list_application(client, session):
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Acme",
            "role": "Dev",
            "vacancy_text": "Текст вакансии",
            "cv_markdown": "# CV",
            "cover_letter": "# Cover",
            "slug": "acme-dev",
            "generated_prompt": "Ты — помощник... МАСТЕР-CV: # CV\nFlutter",
        },
    )
    assert res.status_code == 201
    app_id = res.json()["id"]

    # список
    res = await client.get("/api/admin/applications", headers=VALID)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["company"] == "Acme"
    assert "vacancy_text" not in data[0]  # приватное

    # детальная
    res = await client.get(f"/api/admin/applications/{app_id}", headers=VALID)
    assert res.status_code == 200
    detail = res.json()
    assert detail["vacancy_text"] == "Текст вакансии"
    assert detail["cv_markdown"] == "# CV"
    assert detail["generated_prompt"] == "Ты — помощник... МАСТЕР-CV: # CV\nFlutter"


@pytest.mark.asyncio
async def test_admin_publish_application(client, session):
    # создаём черновик с плейсхолдером ссылки в cover letter
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "X", "role": "R", "vacancy_text": "v",
            "cv_markdown": "# m",
            "cover_letter": "Здравствуйте!\nМоё CV: {CV_LINK}",
            "slug": "x-1",
        },
    )
    app_id = res.json()["id"]
    # публикуем
    res = await client.post(f"/api/admin/applications/{app_id}/publish", headers=VALID)
    assert res.status_code == 200
    data = res.json()
    assert "code" in data
    assert data["url"].startswith("https://")
    short_url = data["url"]
    # плейсхолдер {CV_LINK} должен быть заменён на реальную короткую ссылку
    detail = (await client.get(f"/api/admin/applications/{app_id}", headers=VALID)).json()
    assert "{CV_LINK}" not in detail["cover_letter"], "плейсхолдер не заменён"
    assert short_url in detail["cover_letter"], "ссылка не вставлена в cover letter"


@pytest.mark.asyncio
async def test_admin_archive_application(client, session):
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Z", "role": "R", "vacancy_text": "v",
            "cv_markdown": "# m", "cover_letter": "", "slug": "z-1",
        },
    )
    app_id = res.json()["id"]
    res = await client.post(f"/api/admin/applications/{app_id}/archive", headers=VALID)
    assert res.status_code == 200
    assert res.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_admin_interview_crud(client, session):
    """CRUD интервью: создать → в detail → patch → delete."""
    # создаём отклик
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Int", "role": "Dev", "vacancy_text": "v",
            "cv_markdown": "# m", "cover_letter": "", "slug": "int-1",
        },
    )
    app_id = res.json()["id"]

    # создаём интервью
    res = await client.post(
        f"/api/admin/applications/{app_id}/interviews",
        headers=VALID,
        json={"scheduled_at": "2026-08-01T12:00:00Z", "notes_before": "подготовить стек"},
    )
    assert res.status_code == 201
    iv_id = res.json()["id"]
    assert res.json()["notes_before"] == "подготовить стек"

    # интервью появляется в detail отклика
    detail = (await client.get(f"/api/admin/applications/{app_id}", headers=VALID)).json()
    assert len(detail["interviews"]) == 1
    assert detail["interviews"][0]["id"] == iv_id

    # редактируем
    res = await client.patch(
        f"/api/admin/interviews/{iv_id}",
        headers=VALID,
        json={"notes_after": "прошло хорошо"},
    )
    assert res.status_code == 200
    assert res.json()["notes_after"] == "прошло хорошо"

    # удаляем
    res = await client.delete(f"/api/admin/interviews/{iv_id}", headers=VALID)
    assert res.status_code == 204

    # больше нет в detail
    detail = (await client.get(f"/api/admin/applications/{app_id}", headers=VALID)).json()
    assert len(detail["interviews"]) == 0


@pytest.mark.asyncio
async def test_admin_upcoming_interviews(client, session):
    """Дашборд: upcoming возвращает только будущие интервью."""
    # отклик + интервью в будущем
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Up", "role": "Dev", "vacancy_text": "v",
            "cv_markdown": "# m", "cover_letter": "", "slug": "up-1",
        },
    )
    app_id = res.json()["id"]
    await client.post(
        f"/api/admin/applications/{app_id}/interviews",
        headers=VALID,
        json={"scheduled_at": "2099-12-31T10:00:00Z"},
    )

    # upcoming
    res = await client.get("/api/admin/upcoming", headers=VALID)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["application_role"] == "Dev"
    assert data[0]["application_company"] == "Up"


# ===== Тесты артефактов конкурсных откликов =====


@pytest.mark.asyncio
async def test_upload_and_download_artifact(client, session):
    """Загрузка артефакта → публичная ссылка → скачивание."""
    # создаём отклик
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Test", "role": "Dev", "vacancy_text": "v",
            "cv_markdown": "# m", "cover_letter": "", "slug": "art-1",
        },
    )
    app_id = res.json()["id"]

    # загружаем файл
    res = await client.post(
        f"/api/admin/applications/{app_id}/artifacts",
        headers=VALID,
        files={"file": ("clapgo.apk", b"FAKE_APK_BYTES_12345", "application/vnd.android.package-archive")},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["filename"] == "clapgo.apk"
    assert data["size_bytes"] > 0
    assert "/dl/" in data["download_url"]
    code = data["code"]
    artifact_id = data["id"]

    # артефакт виден в деталях отклика
    detail = (await client.get(f"/api/admin/applications/{app_id}", headers=VALID)).json()
    assert len(detail["artifacts"]) == 1
    assert detail["artifacts"][0]["code"] == code

    # публичное скачивание (без admin-auth)
    res = await client.get(f"/dl/{code}")
    assert res.status_code == 200
    assert b"FAKE_APK" in res.content
    assert "attachment" in res.headers.get("content-disposition", "")

    # удаление
    res = await client.delete(f"/api/admin/artifacts/{artifact_id}", headers=VALID)
    assert res.status_code == 204
    # больше не скачивается
    res = await client.get(f"/dl/{code}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_artifact_archived_gone(client, session):
    """Архивированный отклик → 410 Gone при скачивании артефакта."""
    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Gone", "role": "Dev", "vacancy_text": "v",
            "cv_markdown": "# m", "cover_letter": "", "slug": "art-gone",
        },
    )
    app_id = res.json()["id"]

    res = await client.post(
        f"/api/admin/applications/{app_id}/artifacts",
        headers=VALID,
        files={"file": ("test.zip", b"ZIP_DATA", "application/zip")},
    )
    code = res.json()["code"]

    # архивируем
    await client.post(f"/api/admin/applications/{app_id}/archive", headers=VALID)

    # скачивание → 410
    res = await client.get(f"/dl/{code}")
    assert res.status_code == 410


@pytest.mark.asyncio
async def test_artifact_size_limit(client, session, monkeypatch):
    """Превышение лимита размера → 400."""
    from app.config import settings as cfg
    monkeypatch.setattr(cfg, "artifact_max_size_mb", 0)  # 0 MB = 0 bytes max

    res = await client.post(
        "/api/admin/applications",
        headers=VALID,
        json={
            "company": "Big", "role": "Dev", "vacancy_text": "v",
            "cv_markdown": "# m", "cover_letter": "", "slug": "art-big",
        },
    )
    app_id = res.json()["id"]

    res = await client.post(
        f"/api/admin/applications/{app_id}/artifacts",
        headers=VALID,
        files={"file": ("big.apk", b"X" * 100, "application/octet-stream")},
    )
    assert res.status_code == 400
