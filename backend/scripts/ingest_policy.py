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

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.config import settings
from backend.db.store import get_session, init_db
from backend.db.orm_models import PolicyEmbeddingORM

EMBEDDING_MODEL  = "text-embedding-3-small"
INGESTED_MARKER  = Path(__file__).parent.parent.parent / "docs" / "policy" / ".ingested.json"

SUPPORTED_LOADERS = {
    ".pdf": PyPDFLoader,
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


def ingest(file_path: str) -> int:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_LOADERS:
        raise ValueError(f"지원하지 않는 형식: {suffix}")

    # 마커 파일로 완전 완료 여부 빠르게 확인 (청킹 없이)
    marker = _load_marker()
    if path.name in marker:
        print(f"  이미 완료됨 ({marker[path.name]}청크), 스킵")
        return marker[path.name]

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

    # 이미 저장된 ID 조회 → 누락된 것만 임베딩
    for chunk in chunks:
        chunk["id"] = hashlib.md5(
            f"{chunk['source']}_{chunk['content'][:50]}".encode()
        ).hexdigest()

    init_db()
    with get_session() as db:
        from sqlalchemy import text as sqlt
        rows = db.execute(sqlt("SELECT id FROM policy_embeddings")).fetchall()
    existing_ids = {r[0] for r in rows}

    new_chunks = [c for c in chunks if c["id"] not in existing_ids]
    if not new_chunks:
        print(f"  DB에 모두 저장됨, 마커 기록 후 스킵")
        _save_marker(path.name, total)
        return total

    print(f"  누락 청크: {len(new_chunks)}개 임베딩 생성 중 ({EMBEDDING_MODEL})...")
    embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=settings.openai_api_key)
    vectors = embeddings_model.embed_documents([c["content"] for c in new_chunks])

    print(f"  PostgreSQL 저장 중...")
    with get_session() as db:
        for chunk, vector in zip(new_chunks, vectors):
            stmt = pg_insert(PolicyEmbeddingORM).values(
                id          = chunk["id"],
                content     = chunk["content"],
                parent_text = chunk["parent_text"],
                metadata_   = {"source": chunk["source"], "parent_id": chunk["parent_id"]},
                embedding   = vector,
            ).on_conflict_do_nothing(index_elements=["id"])
            db.execute(stmt)

    # 완료 마커 저장
    _save_marker(path.name, total)
    print(f"  완료 마커 저장: {path.name} ({total}청크)")

    return total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"파일 처리 중: {file_path}")
    count = ingest(file_path)
    print(f"\n완료: {count}개 청크가 PostgreSQL pgvector에 저장됐습니다.")
