from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.db.orm_models import Base

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    _enable_vector()
    Base.metadata.create_all(bind=engine)
    _seed_sync_log()


def _enable_vector() -> None:
    """pgvector 확장 활성화. 미설치 환경(로컬 개발)에서는 스킵."""
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        # 로컬 PostgreSQL에 pgvector 미설치 시 policy_embeddings 테이블만 비활성화
        import logging
        logging.warning(
            "pgvector 확장 없음 — policy_embeddings 테이블 생성 스킵. "
            "사내 규정 검색은 Docker 환경에서만 동작합니다."
        )
        from backend.db.orm_models import Base, PolicyEmbeddingORM
        Base.metadata.remove(PolicyEmbeddingORM.__table__)


def _seed_sync_log() -> None:
    sources = ["gmail", "slack", "jira", "notion", "calendar"]
    with engine.begin() as conn:
        for src in sources:
            conn.execute(
                text("INSERT INTO sync_log (source, status, items_count) VALUES (:s, 'idle', 0) ON CONFLICT (source) DO NOTHING"),
                {"s": src},
            )


@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
