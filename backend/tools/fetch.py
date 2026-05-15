"""
fetch 툴 — 담당 #2 (gmail), #3 (slack, calendar).
커넥터를 래핑해 파이프라인이 호출하는 단일 진입점을 제공한다.
Week 2에서 httpx 실제 호출로 교체 시 async로 전환.
"""
from datetime import datetime, timedelta, timezone

from backend.models import WorkItem

_NOW = datetime.now(timezone.utc)


def fetch_gmail(since_days: int) -> list[WorkItem]:
    # TODO: connectors/gmail.py 구현 후 교체
    now = datetime.now(timezone.utc)
    return [
        WorkItem(
            source="gmail", raw_id="g-001",
            from_email="ceo@example.com", from_name="김대표",
            subject="계약서 최종 서명 요청",
            body_snippet="계약서 서명 부탁드립니다. 마감이 지났습니다.",
            received_at=now - timedelta(days=2),
            due_at=now - timedelta(hours=6),
        ),
        WorkItem(
            source="gmail", raw_id="g-002",
            from_email="dev@company.com", from_name="이개발",
            subject="PROJ-402 배포 승인 대기",
            body_snippet="배포 승인 부탁드립니다. 마감 초과 상태입니다.",
            received_at=now - timedelta(days=1),
            due_at=now - timedelta(days=1),
        ),
        WorkItem(
            source="gmail", raw_id="g-003",
            from_email="newsletter@industry.com", from_name="뉴스레터",
            subject="주간 업계 동향",
            body_snippet="이번 주 업계 소식입니다. FYI.",
            received_at=now - timedelta(days=3),
        ),
    ]


def fetch_slack(since_days: int) -> list[WorkItem]:
    # TODO: connectors/slack.py 구현 후 교체
    now = datetime.now(timezone.utc)
    return [
        WorkItem(
            source="slack", raw_id="s-001",
            from_email="lead@company.com", from_name="박팀장",
            subject="예산 승인 요청",
            body_snippet="박팀장 DM 3건 — 예산 승인 요청.",
            received_at=now - timedelta(minutes=30),
        ),
        WorkItem(
            source="slack", raw_id="s-002",
            from_email="design@company.com", from_name="최디자인",
            subject="UI 피드백 요청",
            body_snippet="디자인팀 — UI 피드백 요청. 오늘까지.",
            received_at=now - timedelta(hours=5),
        ),
    ]


def fetch_calendar(since_days: int) -> list[WorkItem]:
    # TODO: connectors/calendar.py 구현 후 교체
    return []


def fetch_messages(source: str, since_days: int) -> list[WorkItem]:
    """파이프라인 진입점. source에 따라 각 fetch 함수로 라우팅."""
    dispatch = {
        "gmail": fetch_gmail,
        "slack": fetch_slack,
        "calendar": fetch_calendar,
    }
    fn = dispatch.get(source)
    if fn is None:
        return []
    return fn(since_days)
