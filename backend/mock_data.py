"""
USE_MOCK_DATA=true 시 사용하는 샘플 데이터.
담당 #6 (Streamlit UI)이 실제 API 없이 UI 개발할 때 활용.
"""
from datetime import datetime, timedelta, timezone

from backend.models import BriefingHeader, BriefingResult, WorkCard

_NOW = datetime.now(timezone.utc)


def get_mock_briefing() -> BriefingResult:
    cards = [
        WorkCard(
            id="mock-001",
            source="gmail",
            summary="CEO 김대표 — 계약서 서명 요청. 마감일 초과.",
            urgency_level=5,
            urgency_breakdown={"T": 1.0, "A": 0.95, "F": 0.60, "K": 0.90, "S": 0.65},
            action_type="approve",
            from_person="김대표",
            received_at=_NOW - timedelta(days=2),
            estimated_minutes=10,
            due_at=_NOW - timedelta(hours=6),
        ),
        WorkCard(
            id="mock-002",
            source="slack",
            summary="박팀장 DM 3건 — 예산 승인 요청.",
            urgency_level=5,
            urgency_breakdown={"T": 0.85, "A": 0.80, "F": 0.75, "K": 0.70, "S": 0.85},
            action_type="reply",
            from_person="박팀장",
            received_at=_NOW - timedelta(minutes=30),
            estimated_minutes=10,
        ),
        WorkCard(
            id="mock-003",
            source="gmail",
            summary="PROJ-402 배포 승인 대기 — 마감 초과.",
            urgency_level=4,
            urgency_breakdown={"T": 0.95, "A": 0.50, "F": 0.40, "K": 0.60, "S": 0.65},
            action_type="approve",
            from_person="이개발",
            received_at=_NOW - timedelta(days=1),
            estimated_minutes=5,
            due_at=_NOW - timedelta(days=1),
        ),
        WorkCard(
            id="mock-004",
            source="slack",
            summary="디자인팀 — UI 피드백 요청. 오늘까지.",
            urgency_level=3,
            urgency_breakdown={"T": 0.60, "A": 0.40, "F": 0.20, "K": 0.30, "S": 0.50},
            action_type="review",
            from_person="최디자인",
            received_at=_NOW - timedelta(hours=5),
            estimated_minutes=15,
        ),
        WorkCard(
            id="mock-005",
            source="gmail",
            summary="주간 뉴스레터 — 업계 동향.",
            urgency_level=1,
            urgency_breakdown={"T": 0.10, "A": 0.10, "F": 0.00, "K": -0.20, "S": 0.30},
            action_type="fyi",
            from_person="뉴스레터",
            received_at=_NOW - timedelta(days=3),
            estimated_minutes=5,
        ),
    ]
    header = BriefingHeader(
        briefing_id="mock-001",
        absence_days=4,
        total=len(cards),
        urgent=2,
        estimated_minutes=45,
        contacts_needed=[
            {"person": "김대표", "reason": "계약서 서명 마감 초과", "channel": "gmail"},
            {"person": "박팀장", "reason": "예산 승인 DM 미응답", "channel": "slack"},
        ],
        summary_text="4일 부재 동안 5건 수신. 계약서 서명과 예산 승인이 긴급합니다.",
    )
    return BriefingResult(header=header, cards=cards)
