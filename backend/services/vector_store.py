"""
벡터 스토어 서비스 — n8n의 vectorStoreInMemory 노드 대응.

규정집(rules_vector_store_key)과 업무(work_vector_store_key) 두 개의
독립 스토어를 싱글턴으로 관리한다.

Phase 1: 키워드 기반 유사도(TF-IDF 없이 단순 overlap).
Phase 2 전환 시 OpenAI Embeddings + cosine similarity로 교체.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


StoreKey = Literal["rules", "work"]


@dataclass
class Document:
    content: str
    metadata: dict = field(default_factory=dict)


class InMemoryVectorStore:
    """단순 키워드 검색 기반 인메모리 스토어."""

    def __init__(self) -> None:
        self._docs: list[Document] = []

    def insert(self, content: str, metadata: dict | None = None) -> None:
        self._docs.append(Document(content=content, metadata=metadata or {}))

    def retrieve(self, query: str, top_k: int = 3) -> list[Document]:
        """질의 키워드와 겹치는 문서를 점수 순으로 반환."""
        # TODO: Phase 2 — OpenAI Embeddings + cosine similarity로 교체
        query_words = set(query.lower().split())
        scored = []
        for doc in self._docs:
            doc_words = set(doc.content.lower().split())
            score = len(query_words & doc_words)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def clear(self) -> None:
        self._docs.clear()

    def __len__(self) -> int:
        return len(self._docs)


# 싱글턴 스토어 인스턴스
_stores: dict[StoreKey, InMemoryVectorStore] = {
    "rules": InMemoryVectorStore(),
    "work": InMemoryVectorStore(),
}


def get_store(key: StoreKey) -> InMemoryVectorStore:
    return _stores[key]
