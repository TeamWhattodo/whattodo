"""Google Calendar 일정 → WorkItem 목록 변환"""
import hashlib
from datetime import datetime, timezone, timedelta
from googleapiclient.discovery import build
from backend.google_auth import get_credentials
from backend.models import WorkItem


def fetch_calendar(days: int = 7) -> list[WorkItem]:
    creds = get_credentials()
    if not creds:
        return []

    service = build("calendar", "v3", credentials=creds)
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days)

    events = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )

    items: list[WorkItem] = []
    for event in events:
        item = _parse_event(event)
        if item:
            items.append(item)
    return items


def search_calendar_events(query: str = "", days: int = 30) -> list[dict]:
    """제목 키워드로 Google Calendar 이벤트를 검색해 event_id 포함 목록 반환."""
    creds = get_credentials()
    if not creds or not creds.valid:
        return []

    service = build("calendar", "v3", credentials=creds)
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days)

    events = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            q=query,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )

    return [
        {
            "event_id": e["id"],
            "title": e.get("summary", "(제목 없음)"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
            "html_link": e.get("htmlLink"),
        }
        for e in events
    ]


def _parse_event(event: dict) -> WorkItem | None:
    title = event.get("summary", "(제목 없음)")
    organizer = event.get("organizer", {}).get("email", "")
    start = event.get("start", {})

    start_str = start.get("dateTime") or start.get("date", "")
    try:
        if "T" in start_str:
            due_at = datetime.fromisoformat(start_str.replace("Z", "+00:00")).replace(tzinfo=None)
        else:
            due_at = datetime.strptime(start_str, "%Y-%m-%d")
    except Exception:
        due_at = None

    raw = f"일정: {title}\n주최자: {organizer}\n시작: {start_str}"

    return WorkItem(
        id=hashlib.md5(event["id"].encode()).hexdigest(),
        source="calendar",
        raw_content=raw,
        summary=f"[일정] {title}",
        urgency_level=3,
        action_type="review",
        from_person=organizer or None,
        due_at=due_at,
        created_at=datetime.utcnow(),
    )
