from datetime import datetime, timedelta, timezone

import pytest

from app.models import CVVariant, CVVariantStatus, MasterCV, ShortLink


async def _make_link(session, *, expires_in=7, max_hits=None, hit_count=0):
    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    v = CVVariant(
        master_cv_id=1,
        slug="staffty",
        title="t",
        content_markdown="# m",
        status=CVVariantStatus.active,
    )
    session.add(v)
    await session.commit()
    await session.refresh(v)
    link = ShortLink(
        code="R8H",
        cv_variant_id=v.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in),
        max_hits=max_hits,
        hit_count=hit_count,
    )
    session.add(link)
    await session.commit()
    return link


@pytest.mark.asyncio
async def test_resolve_link_success(client, session):
    await _make_link(session)
    res = await client.get("/api/links/resolve", params={"code": "R8H"})
    assert res.status_code == 200
    data = res.json()
    assert data["cv_variant_slug"] == "staffty"
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_resolve_link_expired_410(client, session):
    await _make_link(session, expires_in=-1)
    res = await client.get("/api/links/resolve", params={"code": "R8H"})
    assert res.status_code == 410
    assert res.json()["error"] == "gone"


@pytest.mark.asyncio
async def test_resolve_link_max_hits_410(client, session):
    await _make_link(session, max_hits=5, hit_count=5)
    res = await client.get("/api/links/resolve", params={"code": "R8H"})
    assert res.status_code == 410


@pytest.mark.asyncio
async def test_resolve_unknown_code_404(client):
    res = await client.get("/api/links/resolve", params={"code": "ZZZZ"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_resolve_increments_hit_count_and_logs_hit(client, session):
    link = await _make_link(session, max_hits=10, hit_count=0)
    res = await client.get("/api/links/resolve", params={"code": "R8H"})
    assert res.status_code == 200
    await session.refresh(link)
    assert link.hit_count == 1  # инкремент
    # аналитика записана (ip_hash, не сырой IP)
    from app.models import LinkHit
    from sqlalchemy import select

    hits = (await session.execute(select(LinkHit))).scalars().all()
    assert len(hits) == 1
    assert hits[0].ip_hash is not None  # приватность: хэш, не сырой IP
