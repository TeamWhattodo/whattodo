"""
classify 툴 — 담당 #5.
LLM Fast 1-shot. 항목당 ~200 토큰.
긴급도는 scoring 툴이 이미 계산했으므로 의미 이해만 담당.
"""
from backend.models import WorkItem, WorkCard


async def classify_item(item: WorkItem, urgency_level: int, urgency_breakdown: dict) -> WorkCard:
    """WorkItem → WorkCard 변환. LLM Fast 티어 호출."""
    ...


async def classify_items(item_ids: list[str]) -> list[WorkCard]:
    """Briefing Agent의 classify_items 툴 호출 진입점."""
    ...
