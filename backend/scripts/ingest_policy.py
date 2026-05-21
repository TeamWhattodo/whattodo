"""
사내 규정 문서를 ChromaDB에 임베딩·저장하는 스크립트.

사용법:
    uv run python backend/scripts/ingest_policy.py <파일경로>

예시:
    uv run python backend/scripts/ingest_policy.py docs/사규집.pdf

신규 문서 추가 시 재실행하면 기존 컬렉션에 누적된다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from backend.config import settings

POLICY_STORE_DIR = Path(__file__).parent.parent / "db" / "data" / "policy_store"
EMBEDDING_MODEL = "text-embedding-3-small"

SUPPORTED_LOADERS = {
    ".pdf": PyPDFLoader,
    # ".docx": Docx2txtLoader,    # 추후: pip install docx2txt
    # ".md": TextLoader,          # 추후
    # ".html": BSHTMLLoader,      # 추후
}


def ingest(file_path: str) -> int:
    """
    문서를 청크로 분할해 ChromaDB에 저장한다.
    반환: 저장된 청크 수
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_LOADERS:
        raise ValueError(f"지원하지 않는 형식: {suffix}. 지원 형식: {list(SUPPORTED_LOADERS)}")

    print(f"  로더: {suffix}")
    loader = SUPPORTED_LOADERS[suffix](str(path))
    docs = loader.load()
    print(f"  페이지 수: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    chunks = splitter.split_documents(docs)
    print(f"  청크 수: {len(chunks)}")

    print(f"  임베딩 모델: {EMBEDDING_MODEL}")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=settings.openai_api_key)

    print(f"  ChromaDB 저장 중: {POLICY_STORE_DIR}")
    POLICY_STORE_DIR.mkdir(parents=True, exist_ok=True)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(POLICY_STORE_DIR),
    )
    return len(chunks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"파일 처리 중: {file_path}")
    count = ingest(file_path)
    print(f"\n완료: {count}개 청크가 ChromaDB에 저장됐습니다.")
    print(f"저장 위치: {POLICY_STORE_DIR}")
