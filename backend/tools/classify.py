"""
classify 툴 — 담당 #5.
MVP: rule-based 분류. Week 2에서 LLM Fast 1-shot으로 전환 시 async 추가.
"""
from backend.models import WorkCard, WorkItem


def classify_item(item: WorkItem, urgency_level: int, urgency_breakdown: dict) -> WorkCard:
    """WorkItem → WorkCard 변환.
    MVP: rule-based (키워드·소스 기반 action_type + 간단 요약).
    Week 2: llm_client.complete() 호출로 교체.
    """
    ...
