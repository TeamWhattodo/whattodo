"""
사내 규정 문서를 PostgreSQL pgvector에 임베딩·저장하는 스크립트.

사용법:
    uv run python backend/scripts/ingest_policy.py <파일경로>

예시:
    uv run python backend/scripts/ingest_policy.py docs/사규집.pdf
"""
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

EMBEDDING_MODEL = "text-embedding-3-small"

SUPPORTED_LOADERS = {
    ".pdf": PyPDFLoader,
}


def ingest(file_path: str) -> int:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_LOADERS:
        raise ValueError(f"지원하지 않는 형식: {suffix}")

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

    print(f"  부모 청크: {len(parent_docs)}개 / 자식 청크: {len(chunks)}개")

    # 이미 저장된 청크 ID 조회 → 누락된 것만 임베딩
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
        print(f"  이미 모두 저장됨, 스킵")
        return len(chunks)

    print(f"  누락 청크: {len(new_chunks)}개 임베딩 생성 중 ({EMBEDDING_MODEL})...")
    embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=settings.openai_api_key)
    texts = [c["content"] for c in new_chunks]
    vectors = embeddings_model.embed_documents(texts)

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

    return len(chunks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"파일 처리 중: {file_path}")
    count = ingest(file_path)
    print(f"\n완료: {count}개 청크가 PostgreSQL pgvector에 저장됐습니다.")
