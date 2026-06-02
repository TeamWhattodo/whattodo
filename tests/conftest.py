import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.database import Base, get_db


@pytest.fixture(autouse=True)
def _ensure_jwt_secret():
    from backend.config import settings
    settings.jwt_secret = "testsecret"


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "testsecret")
    from backend.config import settings
    settings.jwt_secret = "testsecret"

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async with test_engine.begin() as conn:
        from backend.auth import models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    from backend.main import app
    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await test_engine.dispose()
