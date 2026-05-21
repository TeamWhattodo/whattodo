# Week 1: mock 반환. Week 2: connector 연결로 교체.
from datetime import datetime, timedelta


def fetch_emails(since_hours: int = 24, max_count: int = 50) -> list[dict]:
    """Gmail 미읽음 이메일 수집. Week 2에 실데이터로 교체."""
    # TODO (#2): from backend.connectors.gmail import GmailConnector
    return [
        {
            "id": "email_mock_001",
            "source": "gmail",
            "raw_content": "[Mock] 김대표: 계약서 서명 요청",
            "summary": "",
            "urgency_level": 0,
            "urgency_breakdown": {},
            "action_type": "none",
            "from_person": "김대표",
            "due_at": (datetime.now() + timedelta(hours=18)).isoformat(),
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
        }
    ]


def fetch_slack_messages(since_hours: int = 24, mention_only: bool = True) -> list[dict]:
    """Slack 멘션·DM 수집. Week 2에 실데이터로 교체."""
    # TODO (#2): from backend.connectors.slack import SlackConnector
    return [
        {
            "id": "slack_mock_001",
            "source": "slack",
            "raw_content": "[Mock] 박팀장 DM: 예산 승인 요청",
            "summary": "",
            "urgency_level": 0,
            "urgency_breakdown": {},
            "action_type": "none",
            "from_person": "박팀장",
            "due_at": None,
            "status": "pending",
            "created_at": (datetime.now() - timedelta(hours=5)).isoformat(),
        }
    ]


def fetch_calendar_events(date_range: int = 3) -> list[dict]:
    """캘린더 일정 수집. Week 2에 실데이터로 교체."""
    # TODO (#2): from backend.connectors.calendar import CalendarConnector
    return [
        {
            "id": "cal_mock_001",
            "source": "calendar",
            "raw_content": "[Mock] 오후 2시 팀 미팅",
            "summary": "",
            "urgency_level": 0,
            "urgency_breakdown": {},
            "action_type": "none",
            "from_person": None,
            "due_at": (datetime.now() + timedelta(hours=4)).isoformat(),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
    ]


def fetch_jira_issues(due_within_days: int = 7, max_count: int = 50) -> list[dict]:
    """Jira 이슈 수집. Week 2에 실데이터로 교체."""
    # TODO (#2): from backend.connectors.jira import JiraConnector
    return [
        {
            "id": "jira_mock_001",
            "source": "jira",
            "raw_content": "[Mock][PROJ-402] 배포 승인 대기",
            "summary": "",
            "urgency_level": 0,
            "urgency_breakdown": {},
            "action_type": "none",
            "from_person": "개발팀",
            "due_at": (datetime.now() - timedelta(hours=3)).isoformat(),
            "status": "pending",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
        }
    ]


def fetch_uploaded_file(file_path: str, file_type: str = "csv") -> dict:
    """업로드된 파일 파싱. Week 2에 실로직으로 교체."""
    # TODO (#2): 파일 타입별 파서 연결
    return {"file_path": file_path, "file_type": file_type, "rows": [], "parsed": False}


if __name__ == "__main__":
    print(f"Gmail:    {len(fetch_emails())}건")
    print(f"Slack:    {len(fetch_slack_messages())}건")
    print(f"Calendar: {len(fetch_calendar_events())}건")
    print(f"Jira:     {len(fetch_jira_issues())}건")
