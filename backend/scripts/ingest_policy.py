"""
사내 규정 문서를 PostgreSQL pgvector에 임베딩·저장하는 스크립트.

사용법:
    uv run python backend/scripts/ingest_policy.py <파일경로>

예시:
    uv run python backend/scripts/ingest_policy.py docs/사규집.pdf
"""
import json
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.dialects.postgresql import insert as pg_insert
import subprocess

from backend.config import settings
from backend.db.store import get_session, init_db
from backend.db.orm_models import PolicyEmbeddingORM

EMBEDDING_MODEL  = "text-embedding-3-small"
INGESTED_MARKER  = Path(__file__).parent.parent.parent / "docs" / "policy" / ".ingested.json"

class CustomHWPLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self):
        try:
            if self.file_path.lower().endswith(".hwpx"):
                import zipfile
                import re
                with zipfile.ZipFile(self.file_path, 'r') as zf:
                    text_parts = []
                    for filename in zf.namelist():
                        if filename.startswith("Contents/section") and filename.endswith(".xml"):
                            xml_content = zf.read(filename).decode('utf-8')
                            text = re.sub(r'<[^>]+>', '', xml_content)
                            text_parts.append(text)
                    full_text = "\n".join(text_parts)
                return [Document(page_content=full_text, metadata={"source": Path(self.file_path).name})]
            else:
                result = subprocess.run(["hwp5txt", self.file_path], capture_output=True, text=True, encoding="utf-8")
                if result.returncode == 0:
                    text = result.stdout
                    return [Document(page_content=text, metadata={"source": Path(self.file_path).name})]
                else:
                    print(f"HWP extraction error: {result.stderr}")
                    return []
        except Exception as e:
            print(f"HWP extraction exception: {e}")
            return []

SUPPORTED_LOADERS = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc": Docx2txtLoader,
    ".hwp": CustomHWPLoader,
    ".hwpx": CustomHWPLoader,
}


def _load_marker() -> dict:
    if INGESTED_MARKER.exists():
        try:
            return json.loads(INGESTED_MARKER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_marker(filename: str, chunk_count: int) -> None:
    data = _load_marker()
    data[filename] = chunk_count
    INGESTED_MARKER.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def is_fully_ingested(filename: str, expected_count: int | None = None) -> bool:
    """마커 파일 기준으로 완전 완료 여부 확인. expected_count 없으면 마커 존재 여부만 확인."""
    data = _load_marker()
    if filename not in data:
        return False
    if expected_count is not None:
        return data[filename] == expected_count
    return True


def ingest(file_path: str, progress_cb=None) -> int:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_LOADERS:
        raise ValueError(f"지원하지 않는 형식: {suffix}")

    # 마커 파일로 완전 완료 여부 확인하되, DB에 실제 데이터가 있는지 검증
    marker = _load_marker()
    if path.name in marker:
        expected_chunks = marker[path.name]
        try:
            with get_session() as db:
                from sqlalchemy import text as sqlt
                row = db.execute(
                    sqlt("SELECT count(*) FROM policy_embeddings WHERE metadata->>'source' = :source"), 
                    {"source": path.name}
                ).fetchone()
                db_count = row[0] if row else 0
            
            if db_count >= expected_chunks:
                print(f"  이미 DB에 완료됨 ({db_count}청크), 스킵")
                return db_count
            else:
                print(f"  마커는 존재하나 DB 청크 부족 ({db_count}/{expected_chunks}), 재임베딩 진행")
        except Exception as e:
            print(f"  DB 확인 실패 ({e}), 재임베딩 진행")

    print(f"  로더: {suffix}")
    loader = SUPPORTED_LOADERS[suffix](str(path))
    docs = loader.load()
    print(f"  페이지 수: {len(docs)}")

    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
    child_splitter  = RecursiveCharacterTextSplitter(chunk_size=150,  chunk_overlap=30)

    parent_docs = parent_splitter.split_documents(docs)
    chunks = []
    for p_idx, p_doc in enumerate(parent_docs):
        for c_doc in child_splitter.split_documents([p_doc]):
            chunks.append({
                "content":     c_doc.page_content,
                "parent_text": p_doc.page_content,
                "source":      path.name,
                "parent_id":   f"{path.name}_p{p_idx}",
            })

    total = len(chunks)
    print(f"  부모 청크: {len(parent_docs)}개 / 자식 청크: {total}개")

    for chunk in chunks:
        chunk["id"] = hashlib.md5(
            f"{chunk['source']}_{chunk['content'][:50]}".encode()
        ).hexdigest()

    with get_session() as db:
        from sqlalchemy import text as sqlt
        # 테이블이 없을 수도 있으므로 예외 처리
        try:
            rows = db.execute(sqlt("SELECT id FROM policy_embeddings")).fetchall()
        except Exception:
            rows = []
    existing_ids = {r[0] for r in rows}

    new_chunks = [c for c in chunks if c["id"] not in existing_ids]
    if not new_chunks:
        print(f"  DB에 모두 저장됨, 마커 기록 후 스킵")
        _save_marker(path.name, total)
        return total

    print(f"  누락 청크: {len(new_chunks)}개 임베딩 생성 중 ({EMBEDDING_MODEL})...")
    embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=settings.openai_api_key)
    
    batch_size = 50
    if progress_cb:
        progress_cb(0, len(new_chunks))
        
    print(f"  PostgreSQL 저장 중...")
    for i in range(0, len(new_chunks), batch_size):
        batch = new_chunks[i:i+batch_size]
        vectors = embeddings_model.embed_documents([c["content"] for c in batch])
        
        with get_session() as db:
            for chunk, vector in zip(batch, vectors):
                stmt = pg_insert(PolicyEmbeddingORM).values(
                    id          = chunk["id"],
                    content     = chunk["content"],
                    parent_text = chunk["parent_text"],
                    metadata_   = {"source": chunk["source"], "parent_id": chunk["parent_id"]},
                    embedding   = vector,
                ).on_conflict_do_nothing(index_elements=["id"])
                db.execute(stmt)
            
        if progress_cb:
            progress_cb(min(i+batch_size, len(new_chunks)), len(new_chunks))
        
        # 메인 스레드가 HTTP 요청을 처리할 수 있도록 양보
        import time
        time.sleep(0.1)

    # 완료 마커 저장
    _save_marker(path.name, total)
    print(f"  완료 마커 저장: {path.name} ({total}청크)")

    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="사내 규정 문서 임베딩")
    parser.add_argument("file_path", help="임베딩할 문서 경로")
    parser.add_argument("--progress-file", default=None, help="진행률 JSON 파일 경로")
    args = parser.parse_args()

    progress_file_path = args.progress_file

    def write_progress(current, total):
        if progress_file_path:
            try:
                progress_data = {
                    "current": current,
                    "total": total,
                    "progress": int((current / total) * 100) if total > 0 else 0,
                }
                Path(progress_file_path).write_text(
                    json.dumps(progress_data), encoding="utf-8"
                )
            except Exception:
                pass

    print(f"파일 처리 중: {args.file_path}")
    count = ingest(args.file_path, progress_cb=write_progress)

    # 최종 완료 상태 기록
    if progress_file_path:
        try:
            Path(progress_file_path).write_text(
                json.dumps({"current": count, "total": count, "progress": 100, "status": "done", "count": count}),
                encoding="utf-8",
            )
        except Exception:
            pass

    print(f"\n완료: {count}개 청크가 PostgreSQL pgvector에 저장됐습니다.")
