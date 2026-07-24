from backend.models import WorkItem, ReceiptItem
from datetime import datetime, timedelta

now = datetime.now()

MOCK_WORK_ITEMS: list[dict] = [
    WorkItem(
        id="email_001",
        source="gmail",
        raw_content="김대표: 계약서 최종 서명 요청드립니다. 내일 오전까지 부탁드려요.",
        summary="계약서 서명 요청 — 내일 오전 마감",
        urgency_level=5,
        action_type="approve",
        from_person="김대표",
        due_at=now + timedelta(hours=18),
        status="pending",
        created_at=now - timedelta(hours=2),
    ).model_dump(mode="json"),
    WorkItem(
        id="slack_001",
        source="slack",
        raw_content="박팀장 DM: 이번 주 예산 승인 3건 부탁드립니다.",
        summary="예산 승인 요청 3건",
        urgency_level=4,
        action_type="approve",
        from_person="박팀장",
        due_at=None,
        status="pending",
        created_at=now - timedelta(hours=5),
    ).model_dump(mode="json"),
    WorkItem(
        id="jira_001",
        source="jira",
        raw_content="[PROJ-402] 배포 승인 대기 — 마감 초과",
        summary="PROJ-402 배포 승인 — 마감 초과",
        urgency_level=5,
        action_type="review",
        from_person="개발팀",
        due_at=now - timedelta(hours=3),
        status="pending",
        created_at=now - timedelta(days=1),
    ).model_dump(mode="json"),
]

MOCK_RECEIPTS: list[dict] = [
    ReceiptItem(
        date="2026-05-12",
        merchant="GS칼텍스 강남점",
        amount=85000,
        category="유류비",
        memo="출장 이동",
    ).model_dump(),
    ReceiptItem(
        date="2026-05-12",
        merchant="롯데호텔 레스토랑",
        amount=42000,
        category="식비",
        memo="거래처 식사",
    ).model_dump(mode="json"),
]
