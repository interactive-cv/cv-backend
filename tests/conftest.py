import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession):
    """FastAPI TestClient с переопределённой зависимостью get_session (in-memory SQLite)."""
    from app.main import create_app
    from app.deps import get_session

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def sample_variant(session: AsyncSession):
    """Создаёт мастер-CV + активный cv_variant 'staffty' для тестов."""
    from app.models import CVVariant, CVVariantStatus, MasterCV

    session.add(MasterCV(id=1, summary="s", contacts={}, full_markdown="# CV", version=1))
    v = CVVariant(
        master_cv_id=1,
        slug="staffty",
        title="Flutter Full Stack",
        company="Acme Corp",
        content_markdown="# Acme Corp CV",
        status=CVVariantStatus.active,
    )
    session.add(v)
    await session.commit()
    return v
