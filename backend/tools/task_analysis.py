"""
업무 순서 분석 툴 — n8n의 업무 순서 분석(toolCode) 노드 대응.

WorkCard 목록을 받아 처리 순서·묶음·예상 소요시간을 구조화한다.
에이전트가 브리핑 결과를 가공할 때 호출한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.models import WorkCard


@dataclass
class TaskGroup:
    label: str                    # "지금 당장", "오늘 안에", "이번 주", "FYI"
    cards: list[WorkCard]
    total_minutes: int


@dataclass
class AnalysisResult:
    groups: list[TaskGroup]
    recommended_order: list[str]  # card id 순서
    summary: str


def analyze_task_order(cards: list[WorkCard]) -> AnalysisResult:
    """
    긴급도 레벨 기반으로 그룹을 구성하고 처리 순서를 추천.
    Phase 2: LLM 호출로 컨텍스트 인식 순서 결정으로 전환.
    """
    buckets: dict[str, list[WorkCard]] = {
        "지금 당장": [],
        "오늘 안에": [],
        "이번 주": [],
        "FYI": [],
    }

    for card in cards:
        if card.urgency_level >= 5:
            buckets["지금 당장"].append(card)
        elif card.urgency_level == 4:
            buckets["오늘 안에"].append(card)
        elif card.urgency_level >= 2:
            buckets["이번 주"].append(card)
        else:
            buckets["FYI"].append(card)

    groups = [
        TaskGroup(
            label=label,
            cards=items,
            total_minutes=sum(c.estimated_minutes for c in items),
        )
        for label, items in buckets.items()
        if items
    ]

    recommended_order = [
        card.id
        for group in groups
        for card in group.cards
    ]

    total_minutes = sum(g.total_minutes for g in groups)
    summary = (
        f"총 {len(cards)}건 | "
        + " · ".join(f"{g.label} {len(g.cards)}건" for g in groups)
        + f" | 예상 {total_minutes}분"
    )

    return AnalysisResult(
        groups=groups,
        recommended_order=recommended_order,
        summary=summary,
    )
