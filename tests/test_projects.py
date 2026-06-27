import pytest

from app.models import Project


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_master_cv_not_found(client):
    # мастер-CV не создан → 404 в едином формате ошибок
    res = await client.get("/api/cv/master")
    assert res.status_code == 404
    body = res.json()
    assert body["error"] == "not_found"
    assert "request_id" in body
    res = await client.get("/api/projects")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_projects_returns_ordered(client, session):
    session.add(
        Project(
            title="B-project", period="2025", role="r", tags=["java"],
            short_desc="d", stack=["Spring"], order_idx=1,
        )
    )
    session.add(
        Project(
            title="A-project", period="2024", role="r", tags=["flutter"],
            short_desc="d", stack=["Dart"], order_idx=0,
        )
    )
    await session.commit()

    res = await client.get("/api/projects")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    # сортировка по order_idx
    assert data[0]["title"] == "A-project"
    assert data[1]["title"] == "B-project"
    assert data[0]["tags"] == ["flutter"]
    # id НЕ должен быть в публичном ответе
    assert "id" not in data[0]


@pytest.mark.asyncio
async def test_get_master_cv(client, session):
    from app.models import MasterCV

    session.add(
        MasterCV(
            id=1, summary="Flutter dev", contacts={"email": "a@b.c"},
            full_markdown="# CV", version=1,
        )
    )
    await session.commit()
    res = await client.get("/api/cv/master")
    assert res.status_code == 200
    data = res.json()
    # публичные поля присутствуют
    assert "summary" in data and "contacts" in data
    assert data["summary"] == "Flutter dev"
    # приватных полей нет
    assert "full_markdown" not in data
    assert "vacancy_text" not in data
