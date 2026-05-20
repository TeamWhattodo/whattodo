from pathlib import Path

POLICY_STORE_DIR = Path(__file__).parent.parent / "db" / "data" / "policy_store"
EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"

_vectorstore = None


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        from langchain_community.vectorstores import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        _vectorstore = Chroma(
            persist_directory=str(POLICY_STORE_DIR),
            embedding_function=embeddings,
        )
    return _vectorstore


def search_company_docs(query: str, top_k: int = 3) -> str:
    """
    사내 규정·문서에서 query와 관련된 내용을 검색해 반환한다.
    ChromaDB가 비어 있으면 안내 문구 반환.
    """
    if not POLICY_STORE_DIR.exists():
        return "사내 문서가 아직 등록되지 않았습니다. backend/scripts/ingest_policy.py를 실행해 문서를 먼저 등록해주세요."
    try:
        vs = _get_vectorstore()
        docs = vs.similarity_search(query, k=top_k)
        if not docs:
            return f"'{query}'와 관련된 규정을 찾을 수 없습니다."
        return "\n\n".join(f"[{i+1}] {doc.page_content}" for i, doc in enumerate(docs))
    except Exception as e:
        return f"문서 검색 오류: {e}"


if __name__ == "__main__":
    print(search_company_docs("출장 교통비 한도"))
