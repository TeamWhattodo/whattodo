from pathlib import Path

from backend.config import settings

POLICY_STORE_DIR = Path(__file__).parent.parent / "db" / "data" / "policy_store"
EMBEDDING_MODEL = "text-embedding-3-small"

_vectorstore = None


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=settings.openai_api_key)
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
        # 자식 청크 검색. 부모 매핑을 위해 k=5로 넉넉하게 검색
        docs = vs.similarity_search(query, k=5)
        if not docs:
            return f"'{query}'와 관련된 규정을 찾을 수 없습니다."
            
        seen_parents = set()
        parent_contexts = []
        for doc in docs:
            parent_text = doc.metadata.get('parent_text')
            # 계층적 청킹이 적용안된 옛 문서 호환성을 위해 parent_text가 없으면 page_content 활용
            text_to_use = parent_text if parent_text else doc.page_content
            if text_to_use not in seen_parents:
                seen_parents.add(text_to_use)
                parent_contexts.append(text_to_use)
                
        # 최종 부모 문맥 최대 top_k개 조합
        final_contexts = parent_contexts[:top_k]
        
        return "\n\n".join(f"[{i+1}] {ctx}" for i, ctx in enumerate(final_contexts))
    except Exception as e:
        return f"문서 검색 오류: {e}"


if __name__ == "__main__":
    print(search_company_docs("출장 교통비 한도"))
