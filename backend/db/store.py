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
    "current_file": "",    # 현재 진행 중인 파일
    "progress": 0,         # 0 ~ 100
    "error": None,
}


def init_db() -> None:
    _enable_vector()
    Base.metadata.create_all(bind=engine)
    _seed_sync_log()
    # 서버 기동 시 자동 임베딩 제거 (수동 트리거로 변경)


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
                text("INSERT INTO sync_log (user_id, source, status, items_count) VALUES (1, :s, 'idle', 0) ON CONFLICT (user_id, source) DO NOTHING"),
                {"s": src},
            )


def _run_ingest_policy(filename: str) -> None:
    global policy_ingest_status
    from pathlib import Path

    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    pdf = policy_dir / filename
    if not pdf.exists():
        return

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM policy_embeddings LIMIT 1"))
    except Exception:
        return

    policy_ingest_status["status"] = "running"
    policy_ingest_status["files"] = [filename]
    policy_ingest_status["done_files"] = []
    policy_ingest_status["current_file"] = filename
    policy_ingest_status["progress"] = 0

    def progress_cb(current, total):
        if total > 0:
            policy_ingest_status["progress"] = int((current / total) * 100)

    try:
        from backend.scripts.ingest_policy import ingest
        logging.info(f"[policy] 임베딩 시작: {filename}")
        count = ingest(str(pdf), progress_cb=progress_cb)
        logging.info(f"[policy] 완료: {filename} ({count}청크)")
        policy_ingest_status["done_files"].append(filename)
    except Exception as e:
        logging.error(f"[policy] 임베딩 실패: {filename} — {e}")
        policy_ingest_status["status"] = "error"
        policy_ingest_status["error"] = str(e)
        return

    policy_ingest_status["status"] = "done"
    policy_ingest_status["progress"] = 100


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


def trigger_policy_ingest(filename: str) -> None:
    global policy_ingest_status
    if policy_ingest_status["status"] == "running":
        return
    threading.Thread(target=_run_ingest_policy, args=(filename,), daemon=True).start()


def get_policy_list() -> list:
    from pathlib import Path
    import json
    
    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    if not policy_dir.exists():
        return []
        
    pdfs = list(policy_dir.glob("*.pdf"))
    files = []
    
    marker_path = policy_dir / ".ingested.json"
    marker = {}
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    for pdf in pdfs:
        is_done = pdf.name in marker
        files.append({
            "name": pdf.name,
            "size": pdf.stat().st_size,
            "embedded": is_done,
        })
    return files


def delete_policy_file(filename: str) -> None:
    from pathlib import Path
    import json
    
    if "/" in filename or ".." in filename:
        raise ValueError("Invalid filename")
        
    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    file_path = policy_dir / filename
    
    # 1. 파일 삭제
    if file_path.exists():
        file_path.unlink()
        
    # 2. 마커 파일에서 삭제
    marker_path = policy_dir / ".ingested.json"
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if filename in marker:
                del marker[filename]
                marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
            
    # 3. DB에서 해당 문서의 임베딩 삭제
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM policy_embeddings WHERE metadata->>'source' = :filename"),
            {"filename": filename}
        )

