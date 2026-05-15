"""
scoring 툴 — 담당 #4.
순수 Python. LLM 없음. 항목당 ~1ms.

urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S
urgency_level = ceil(urgency_score × 5)  → 1~5
"""
from backend.models import WorkItem


def calculate_urgency(item: WorkItem) -> tuple[int, dict]:
    """(urgency_level 1~5, breakdown dict) 반환."""
    t = _time_score(item)
    a = _authority_score(item)
    f = _followup_score(item)
    k = _keyword_score(item)
    s = _source_score(item)
    ...


def _time_score(item: WorkItem) -> float:
    ...


def _authority_score(item: WorkItem) -> float:
    ...


def _followup_score(item: WorkItem) -> float:
    ...


def _keyword_score(item: WorkItem) -> float:
    ...


def _source_score(item: WorkItem) -> float:
    ...


async def score_urgency(item_ids: list[str]) -> dict:
    """Briefing Agent의 score_urgency 툴 호출 진입점. item_id → (level, breakdown) 반환."""
    ...
