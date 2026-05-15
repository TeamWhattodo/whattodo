"""
fetch 툴 — 담당 #2 (gmail), #3 (slack, calendar).
커넥터를 래핑해 Briefing Agent가 호출하는 단일 진입점을 제공한다.
"""
from datetime import datetime, timedelta, timezone

from backend.models import WorkItem


async def fetch_gmail(since_days: int) -> list[WorkItem]:
    """Gmail에서 부재 기간 메시지 수집. connectors/gmail.py 위임."""
    ...


async def fetch_slack(since_days: int) -> list[WorkItem]:
    """Slack에서 부재 기간 메시지 수집. connectors/slack.py 위임."""
    ...


async def fetch_calendar(since_days: int) -> list[WorkItem]:
    """Google Calendar에서 부재 기간 이벤트 수집. connectors/calendar.py 위임."""
    ...


async def fetch_messages(source: str, since_days: int) -> list[WorkItem]:
    """Briefing Agent의 fetch_messages 툴 호출 진입점."""
    dispatch = {
        "gmail": fetch_gmail,
        "slack": fetch_slack,
        "calendar": fetch_calendar,
    }
    fn = dispatch.get(source)
    if fn is None:
        return []
    return await fn(since_days)
