import pytest
from sqlalchemy import select

from app.db import Base
from app.models import (
    CVVariant,
    CVVariantStatus,
    LinkHit,
    MasterCV,
    Project,
    ShortLink,
)
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_create_cv_variant_roundtrip(session):
    master = MasterCV(
        summary="test summary",
        contacts={"email": "a@b.c"},
        full_markdown="# CV",
        version=1,
    )
    session.add(master)
    await session.commit()
    await session.refresh(master)

    variant = CVVariant(
        master_cv_id=master.id,
        slug="staffty",
        title="Flutter Full Stack",
        company="Acme Corp",
        content_markdown="# CV for Acme Corp",
        status=CVVariantStatus.active,
    )
    session.add(variant)
    await session.commit()

    loaded = (
        await session.execute(select(CVVariant).where(CVVariant.slug == "staffty"))
    ).scalar_one()
    assert loaded.id is not None
    assert loaded.company == "Acme Corp"
    assert loaded.status == CVVariantStatus.active


@pytest.mark.asyncio
async def test_all_tables_creatable(session):
    """Все 5 таблиц создаются и принимают данные (кросс-БД типы валидны)."""
    assert set(Base.metadata.tables) == {
        "master_cv", "cv_variant", "short_link", "link_hit", "project",
    }

    master = MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1)
    session.add(master)
    await session.commit()

    variant = CVVariant(
        master_cv_id=1, slug="v1", title="t", content_markdown="# m",
        status=CVVariantStatus.active,
    )
    session.add(variant)
    await session.commit()
    await session.refresh(variant)

    link = ShortLink(
        code="R8H", cv_variant_id=variant.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        max_hits=10, hit_count=0,
    )
    session.add(link)
    session.add(LinkHit(short_link_code="R8H", ip_hash="abc"))
    session.add(Project(
        title="P", period="2025", role="r", tags=["flutter", "java"],
        short_desc="d", stack=["Dart", "Spring"], metrics={"rps": 100}, order_idx=0,
    ))
    await session.commit()

    assert (await session.execute(select(ShortLink))).scalar_one().max_hits == 10
    assert (await session.execute(select(LinkHit))).scalar_one().ip_hash == "abc"
    proj = (await session.execute(select(Project))).scalar_one()
    assert proj.tags == ["flutter", "java"]
    assert proj.metrics == {"rps": 100}
