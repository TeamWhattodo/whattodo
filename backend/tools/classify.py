"""
classify 툴 — 담당 #5.
MVP: rule-based 분류. Week 2에서 LLM Fast 1-shot으로 전환.
"""
from backend.models import WorkCard, WorkItem

_ACTION_KEYWORDS: dict[str, list[str]] = {
    "approve": ["승인", "서명", "결재", "approve", "sign"],
    "review":  ["검토", "리뷰", "확인", "review", "feedback"],
    "fyi":     ["fyi", "참고", "공유", "뉴스레터", "동향"],
}


def classify_item(item: WorkItem, urgency_level: int, urgency_breakdown: dict) -> WorkCard:
    """WorkItem → WorkCard 변환.
    MVP: rule-based (키워드·소스 기반 action_type + subject를 요약으로 사용).
    Week 2: llm_client.complete() 호출로 교체.
    """
    text = f"{item.subject} {item.body_snippet}".lower()

    action_type = "reply"
    for action, keywords in _ACTION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            action_type = action
            break

    return WorkCard(
        id=item.id,
        source=item.source,
        summary=item.subject,
        urgency_level=urgency_level,
        urgency_breakdown=urgency_breakdown,
        action_type=action_type,
        from_person=item.from_name,
        received_at=item.received_at,
        estimated_minutes=10,
        due_at=item.due_at,
    )
