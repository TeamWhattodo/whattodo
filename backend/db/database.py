"""SQLAlchemy async 엔진·세션·Base. 인증용 영속 저장소."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

_async_url = (
    settings.database_url
    .replace("postgresql://", "postgresql+asyncpg://", 1)
    .split("?")[0]  # 기존 쿼리 파라미터 제거
)
engine = create_async_engine(_async_url, echo=False, connect_args={"ssl": False})
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """기동 시 테이블 생성 (모델 import 후 호출)."""
    from backend.auth import models  # noqa: F401  (모델 등록)
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for col in ("name", "department", "position"):
            await conn.execute(
                text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} VARCHAR")
            )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청 스코프 DB 세션 의존성."""
    async with SessionLocal() as session:
        yield session
