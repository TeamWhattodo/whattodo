"""
규정집 툴 — n8n의 규정집 Retrieve 노드 대응.

회사 내규, 출장비/유류비 정산 기준, 사내 규정 관련 질문에 답할 때 사용.
벡터 스토어에서 관련 문서 청크를 꺼내 에이전트에 컨텍스트로 전달한다.

Tool description (에이전트에 등록):
  "회사 내규, 출장비/유류비 정산 기준, 사내 규정 관련 질문에 답할 때 사용합니다.
   정책이나 규정 기준이 필요한 경우 이 툴을 호출하세요."
"""
from __future__ import annotations

from backend.services.vector_store import get_store


def retrieve_policy(query: str, top_k: int = 3) -> str:
    """규정집 스토어에서 관련 청크를 검색해 문자열로 반환."""
    store = get_store("rules")
    docs = store.retrieve(query, top_k=top_k)
    if not docs:
        return "관련 규정을 찾지 못했습니다."
    return "\n---\n".join(doc.content for doc in docs)


def load_policy_document(text: str, metadata: dict | None = None) -> int:
    """
    규정집 문서 텍스트를 청크 단위로 스토어에 저장.
    n8n의 규정집 Data Loader → 규정집 Vector Store insert 흐름 대응.
    반환값: 저장된 청크 수.
    """
    store = get_store("rules")
    chunks = _chunk_text(text)
    for chunk in chunks:
        store.insert(chunk, metadata=metadata or {})
    return len(chunks)


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    # TODO: Phase 2 — langchain RecursiveCharacterTextSplitter 등으로 교체
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return chunks
