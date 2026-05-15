"""
scoring 툴 — 담당 #4.
순수 Python. LLM 없음. 항목당 ~1ms.
MVP: T 신호 단독.  확장: 5-신호 가중합으로 전환.
"""
import math

from backend.models import WorkItem


def calculate_urgency(item: WorkItem) -> tuple[int, dict]:
    """(urgency_level 1~5, breakdown dict) 반환."""
    t = _time_score(item)
    level = max(1, min(5, math.ceil(t * 5)))
    return level, {"T": round(t, 3)}


def _time_score(item: WorkItem) -> float:
    """마감 기준 지수 감쇠. 초과=1.0, 24h 후≈0.12, 없음=최대 0.6."""
    ...


# ── 확장용 신호 (Week 3+ 전환 시 calculate_urgency에 추가) ────────────────────

def _authority_score(item: WorkItem) -> float:
    """온보딩 태깅 → 서명 파싱 → 행동 추정 → 기본값 0.4."""
    ...


def _followup_score(item: WorkItem) -> float:
    """미응답 동일 발신자 메시지 수, log 스케일."""
    ...


def _keyword_score(item: WorkItem) -> float:
    """정규식 매칭. "urgent"=+0.9, "FYI"=−0.4."""
    ...


def _source_score(item: WorkItem) -> float:
    """Slack DM=0.85, Jira blocker=0.90, 이메일 CC=0.35."""
    ...
