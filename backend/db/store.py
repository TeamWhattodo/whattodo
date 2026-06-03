import logging
import threading
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

# 임베딩 상태 (프론트 폴링용)
policy_ingest_status = {
    "status": "idle",      # idle | running | done | error
    "files": [],           # 처리 중인 파일 목록
    "done_files": [],      # 완료된 파일 목록
    "error": None,
}


def init_db() -> None:
    _enable_vector()
    Base.metadata.create_all(bind=engine)
    _seed_sync_log()
    # 임베딩은 백그라운드 스레드로 실행 (서버 시작 블로킹 방지)
    threading.Thread(target=_auto_ingest_policies, daemon=True).start()


def _enable_vector() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
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
    global policy_ingest_status
    from pathlib import Path

    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    if not policy_dir.exists():
        return

    pdfs = list(policy_dir.glob("*.pdf"))
    if not pdfs:
        return

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM policy_embeddings LIMIT 1"))
    except Exception:
        return

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT metadata->>'source' FROM policy_embeddings"
        )).fetchall()
    already_ingested = {r[0] for r in rows if r[0]}

    new_pdfs = [p for p in pdfs if p.name not in already_ingested]
    if not new_pdfs:
        policy_ingest_status["status"] = "done"
        return

    policy_ingest_status["status"] = "running"
    policy_ingest_status["files"] = [p.name for p in new_pdfs]
    policy_ingest_status["done_files"] = []

    for pdf in new_pdfs:
        try:
            from backend.scripts.ingest_policy import ingest
            logging.info(f"[policy] 임베딩 시작: {pdf.name}")
            count = ingest(str(pdf))
            logging.info(f"[policy] 완료: {pdf.name} ({count}청크)")
            policy_ingest_status["done_files"].append(pdf.name)
        except Exception as e:
            logging.error(f"[policy] 임베딩 실패: {pdf.name} — {e}")
            policy_ingest_status["status"] = "error"
            policy_ingest_status["error"] = str(e)
            return

    policy_ingest_status["status"] = "done"


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
