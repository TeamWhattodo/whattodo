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
    _auto_ingest_policies()


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


def _auto_ingest_policies() -> None:
    """docs/policy/ 폴더의 PDF를 자동 임베딩. 이미 등록된 파일은 스킵."""
    import logging
    from pathlib import Path

    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    if not policy_dir.exists():
        return

    pdfs = list(policy_dir.glob("*.pdf"))
    if not pdfs:
        return

    # policy_embeddings 테이블이 없으면(pgvector 미설치) 스킵
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM policy_embeddings LIMIT 1"))
    except Exception:
        return

    # 이미 등록된 파일명 조회
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT metadata->>'source' FROM policy_embeddings"
        )).fetchall()
    already_ingested = {r[0] for r in rows if r[0]}

    for pdf in pdfs:
        if pdf.name in already_ingested:
            logging.info(f"[policy] 이미 등록됨, 스킵: {pdf.name}")
            continue
        try:
            from backend.scripts.ingest_policy import ingest
            logging.info(f"[policy] 임베딩 시작: {pdf.name}")
            count = ingest(str(pdf))
            logging.info(f"[policy] 완료: {pdf.name} ({count}청크)")
        except Exception as e:
            logging.error(f"[policy] 임베딩 실패: {pdf.name} — {e}")


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
