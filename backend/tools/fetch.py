"""
fetch 툴 — 담당 #2 (gmail), #3 (slack, calendar).
커넥터를 래핑해 파이프라인이 호출하는 단일 진입점을 제공한다.
Week 2에서 httpx 실제 호출로 교체 시 async로 전환.
"""
from backend.models import WorkItem


def fetch_gmail(since_days: int) -> list[WorkItem]:
    """Gmail에서 부재 기간 메시지 수집. connectors/gmail.py 위임."""
    ...


def fetch_slack(since_days: int) -> list[WorkItem]:
    """Slack에서 부재 기간 메시지 수집. connectors/slack.py 위임."""
    ...


def fetch_calendar(since_days: int) -> list[WorkItem]:
    """Google Calendar에서 부재 기간 이벤트 수집. connectors/calendar.py 위임."""
    ...


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
