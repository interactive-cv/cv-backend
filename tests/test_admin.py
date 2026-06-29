import pytest

from app.config import settings
from app.models import MasterCV

VALID = {"Authorization": f"Bearer {settings.admin_token}"}


@pytest.mark.asyncio
async def test_admin_create_variant_unauthorized_no_token(client):
    # без токена → 401 (а не 422), в едином AppError-формате
    res = await client.post(
        "/admin/variants", json={"slug": "x", "title": "t", "content_markdown": "# m"}
    )
    assert res.status_code == 401
    assert res.json()["error"] == "unauthorized"


@pytest.mark.asyncio
async def test_admin_create_variant_unauthorized_wrong_token(client):
    res = await client.post(
        "/admin/variants",
        json={"slug": "x", "title": "t", "content_markdown": "# m"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_create_variant_success(client, session):
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    await session.commit()
    res = await client.post(
        "/admin/variants",
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
        "/admin/variants",
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
        "/admin/links", headers=VALID, json={"cv_variant_slug": "sber", "ttl_days": 14}
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
        "/admin/links", headers=VALID, json={"cv_variant_slug": "no-such-variant"}
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_variant_persists_and_visible_publicly(client, session):
    """Созданный через admin вариант виден через публичный GET /api/variants/{slug}."""
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    await session.commit()
    res = await client.post(
        "/admin/variants",
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
        "/admin/variants",
        headers=VALID,
        json={"slug": "YANDEX", "title": "t", "content_markdown": "# m"},
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "yandex"
