import pytest


@pytest.mark.asyncio
async def test_get_variant_by_slug_success(client, sample_variant):
    res = await client.get("/api/variants/staffty")
    assert res.status_code == 200
    data = res.json()
    assert data["slug"] == "staffty"
    assert data["company"] == "Acme Corp"
    # vacancy_text НЕ должен утекать в публичный API (§10 приватность)
    assert "vacancy_text" not in data


@pytest.mark.asyncio
async def test_get_variant_archived_returns_404(client, sample_variant, session):
    sample_variant.status = "archived"
    await session.commit()
    res = await client.get("/api/variants/staffty")
    assert res.status_code == 404
    body = res.json()
    assert body["error"] == "not_found"
    # единый формат ошибки (§9)
    assert "message" in body and "request_id" in body


@pytest.mark.asyncio
async def test_get_variant_unknown_slug_404(client):
    res = await client.get("/api/variants/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"] == "not_found"
