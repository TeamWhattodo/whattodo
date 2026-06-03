"""업무 목록 조회 — DB 미구현으로 stub 데이터 반환."""
from datetime import date, timedelta


def fetch_tasks(start: str, end: str) -> dict:
    """지정 기간의 업무 목록을 DB에서 가져온다.
    start/end: YYYY-MM-DD 형식.
    TODO: DB 구현 후 실제 쿼리로 교체.
    """
    start_date = date.fromisoformat(start)
    end_date   = date.fromisoformat(end)

    stub_tasks = [
        {
            "id": "task-001",
            "title": "Q2 마케팅 예산 검토 및 승인",
            "source": "jira",
            "category": "review",
            "date": str(start_date),
            "assignee": "김철수",
            "description": "Q2 마케팅 캠페인 예산안 검토 후 팀장 승인 완료",
        },
        {
            "id": "task-002",
            "title": "신규 온보딩 문서 작성",
            "source": "notion",
            "category": "documentation",
            "date": str(start_date + timedelta(days=1)),
            "assignee": "이영희",
            "description": "신입 사원용 온보딩 가이드 초안 작성 및 공유",
        },
        {
            "id": "task-003",
            "title": "슬랙 채널 권한 정리",
            "source": "slack",
            "category": "admin",
            "date": str(start_date + timedelta(days=2)),
            "assignee": "박민준",
            "description": "#general 채널 권한 재설정, 퇴사자 계정 비활성화",
        },
        {
            "id": "task-004",
            "title": "6월 팀 회식 일정 조율",
            "source": "gmail",
            "category": "coordination",
            "date": str(start_date + timedelta(days=3)),
            "assignee": "김철수",
            "description": "팀원 일정 수합 후 6월 15일 저녁 확정, 장소 예약 완료",
        },
        {
            "id": "task-005",
            "title": "API 응답 속도 이슈 수정",
            "source": "jira",
            "category": "bug_fix",
            "date": str(start_date + timedelta(days=4)),
            "assignee": "이영희",
            "description": "검색 API 응답 지연(p95 3.2s → 0.8s) 원인 분석 및 캐시 레이어 추가",
        },
    ]

    tasks = [t for t in stub_tasks if start_date <= date.fromisoformat(t["date"]) <= end_date]

    return {
        "period": {"start": start, "end": end},
        "tasks": tasks,
        "total": len(tasks),
    }
