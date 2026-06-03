from backend.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"


def search_company_docs(query: str, top_k: int = 3) -> str:
    """
    사내 규정·문서에서 query와 관련된 내용을 pgvector로 검색해 반환한다.
    """
    try:
        from langchain_openai import OpenAIEmbeddings
        from sqlalchemy import text
        from backend.db.store import get_session

        embeddings_model = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=settings.openai_api_key,
        )
        query_vector = embeddings_model.embed_query(query)
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        with get_session() as db:
            rows = db.execute(text("""
                SELECT content, parent_text
                FROM policy_embeddings
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT 5
            """), {"vec": vector_str}).fetchall()

        if not rows:
            return "사내 문서가 아직 등록되지 않았습니다. backend/scripts/ingest_policy.py를 실행해 문서를 먼저 등록해주세요."

        seen, contexts = set(), []
        for content, parent_text in rows:
            text_to_use = parent_text if parent_text else content
            if text_to_use not in seen:
                seen.add(text_to_use)
                contexts.append(text_to_use)

        return "\n\n".join(f"[{i+1}] {ctx}" for i, ctx in enumerate(contexts[:top_k]))

    except Exception as e:
        return f"문서 검색 오류: {e}"


if __name__ == "__main__":
    print(search_company_docs("출장 교통비 한도"))
