import logging
import threading  # fallback용으로 유지
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


async def _run_ingest_policy_async(filename: str) -> None:
    """asyncio 기반 비동기 임베딩 실행 — 이벤트 루프를 블로킹하지 않음"""
    import asyncio
    import sys
    import json
    import tempfile
    from pathlib import Path

    global policy_ingest_status

    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    target_file = policy_dir / filename
    if not target_file.exists():
        return

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM policy_embeddings LIMIT 1"))
    except Exception:
        return

    policy_ingest_status.update({
        "status": "running",
        "files": [filename],
        "done_files": [],
        "current_file": filename,
        "progress": 0,
        "error": None,
    })

    script_path = Path(__file__).parent.parent / "scripts" / "ingest_policy.py"
    project_root = Path(__file__).parent.parent.parent

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="ingest_", delete=False
    ) as pf:
        progress_file = Path(pf.name)

    try:
        # stderr는 PIPE로 받아 버퍼 overflow 없이 비동기 수집
        # stdout은 DEVNULL (디버그 print가 많아 버퍼 블로킹 위험)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path), str(target_file),
            "--progress-file", str(progress_file),
            cwd=str(project_root),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        stderr_lines: list[str] = []

        async def _drain_stderr() -> None:
            try:
                async for line in proc.stderr:
                    stderr_lines.append(line.decode("utf-8", errors="replace"))
            except asyncio.CancelledError:
                pass

        async def _update_progress() -> None:
            try:
                while True:
                    await asyncio.sleep(0.5)
                    if progress_file.exists():
                        try:
                            data = json.loads(progress_file.read_text(encoding="utf-8"))
                            policy_ingest_status["progress"] = data.get("progress", 0)
                        except Exception:
                            pass
            except asyncio.CancelledError:
                pass

        drain_task = asyncio.create_task(_drain_stderr())
        progress_task = asyncio.create_task(_update_progress())

        try:
            await proc.wait()
        finally:
            progress_task.cancel()
            await drain_task  # stderr 마저 읽기

        if proc.returncode == 0:
            count = 0
            if progress_file.exists():
                try:
                    data = json.loads(progress_file.read_text(encoding="utf-8"))
                    count = data.get("count", 0)
                except Exception:
                    pass
            logging.info(f"[policy] 완료: {filename} ({count}청크)")
            policy_ingest_status["done_files"].append(filename)
            policy_ingest_status["status"] = "done"
            policy_ingest_status["progress"] = 100
        else:
            error_msg = "".join(stderr_lines)[-500:] or "Unknown error"
            logging.error(f"[policy] 임베딩 실패: {filename} — {error_msg}")
            policy_ingest_status["status"] = "error"
            policy_ingest_status["error"] = error_msg

    except Exception as e:
        logging.error(f"[policy] 임베딩 실패: {filename} — {e}")
        policy_ingest_status["status"] = "error"
        policy_ingest_status["error"] = str(e)
    finally:
        try:
            if progress_file.exists():
                progress_file.unlink()
        except Exception:
            pass


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
    """동기 컨텍스트용 — 현재 이벤트 루프에 async 태스크를 예약한다."""
    import asyncio
    global policy_ingest_status
    if policy_ingest_status["status"] == "running":
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run_ingest_policy_async(filename))
    except RuntimeError:
        # 이벤트 루프가 없는 컨텍스트(테스트 등)에서는 새 루프로 실행
        threading.Thread(
            target=lambda: asyncio.run(_run_ingest_policy_async(filename)),
            daemon=True,
        ).start()


def get_policy_list() -> list:
    from pathlib import Path
    import json
    
    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    if not policy_dir.exists():
        return []
        
    files_paths = []
    for ext in ("*.pdf", "*.hwp", "*.hwpx", "*.docx", "*.doc"):
        files_paths.extend(policy_dir.glob(ext))
    
    files = []
    
    marker_path = policy_dir / ".ingested.json"
    marker = {}
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    for file_path in files_paths:
        is_done = file_path.name in marker
        files.append({
            "name": file_path.name,
            "size": file_path.stat().st_size,
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

