"""
scoring 툴 — 담당 #4.
순수 Python. LLM 없음. 항목당 ~1ms.
MVP: T 신호 단독.  확장: 5-신호 가중합으로 전환.
"""
import math
from datetime import datetime, timezone

from backend.models import WorkItem


def calculate_urgency(item: WorkItem) -> tuple[int, dict]:
    """(urgency_level 1~5, breakdown dict) 반환."""
    t = _time_score(item)
    level = max(1, min(5, math.ceil(t * 5)))
    return level, {"T": round(t, 3)}


def _time_score(item: WorkItem) -> float:
    """마감 기준 지수 감쇠. 초과=1.0, 24h 후≈0.12, 없음=최대 0.6."""
    now = datetime.now(timezone.utc)
    if item.due_at:
        hours_left = (item.due_at - now).total_seconds() / 3600
        if hours_left <= 0:
            return 1.0
        return 1 - math.exp(-3 / max(hours_left, 0.5))
    else:
        hours_elapsed = (now - item.received_at).total_seconds() / 3600
        return min(hours_elapsed / 72, 0.6)


# ── 확장용 신호 (Week 3+ 전환 시 calculate_urgency에 추가) ────────────────────

def _authority_score(item: WorkItem) -> float:
    ...


def _followup_score(item: WorkItem) -> float:
    ...


def _keyword_score(item: WorkItem) -> float:
    ...


def _source_score(item: WorkItem) -> float:
    ...
