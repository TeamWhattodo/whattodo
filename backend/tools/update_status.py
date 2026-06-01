from backend.tools.storage import update_item_status as _update_status


def update_item_status(item_id: str, status: str) -> dict:
    """
    WorkItem 상태를 변경한다.
    status: done | snoozed | pending
    """
    return _update_status(item_id, status)


def create_calendar_block(title: str, start: str, end: str) -> dict:
    """Google Calendar에 이벤트를 생성한다. Google 미인증 시 mock 반환."""
    from backend.google_auth import get_credentials
    from googleapiclient.discovery import build

    creds = get_credentials()
    if not creds or not creds.valid:
        return {
            "success": False,
            "error": "Google 계정이 연결되지 않았습니다. 사이드바에서 Google 계정을 연결해주세요.",
        }

    service = build("calendar", "v3", credentials=creds)

    # 중복 일정 체크: 같은 시간대에 동일 제목의 이벤트가 있는지 확인
    existing = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start if start.endswith("Z") else start + "+09:00",
            timeMax=end if end.endswith("Z") else end + "+09:00",
            q=title,
            singleEvents=True,
        )
        .execute()
        .get("items", [])
    )
    duplicates = [e for e in existing if e.get("summary") == title]
    if duplicates:
        return {
            "success": False,
            "error": f"동일한 제목의 일정이 이미 존재합니다: {duplicates[0].get('id')}",
            "existing_event_id": duplicates[0].get("id"),
        }

    event_body = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "Asia/Seoul"},
        "end": {"dateTime": end, "timeZone": "Asia/Seoul"},
    }
    created = service.events().insert(calendarId="primary", body=event_body).execute()
    return {
        "success": True,
        "event_id": created.get("id"),
        "title": created.get("summary"),
        "start": created.get("start", {}).get("dateTime"),
        "end": created.get("end", {}).get("dateTime"),
        "html_link": created.get("htmlLink"),
    }


def delete_calendar_block(event_id: str) -> dict:
    """Google Calendar 이벤트를 삭제한다. Google 미인증 시 에러 반환."""
    from backend.google_auth import get_credentials
    from googleapiclient.discovery import build

    creds = get_credentials()
    if not creds or not creds.valid:
        return {
            "success": False,
            "error": "Google 계정이 연결되지 않았습니다. 사이드바에서 Google 계정을 연결해주세요.",
        }

    service = build("calendar", "v3", credentials=creds)
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"success": True, "event_id": event_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_jira_issue(issue_key: str, status: str) -> dict:
    """Jira 이슈 상태를 변경한다. (Phase 2: Jira API 연결)"""
    # TODO (#2): Jira API 연결
    return {"success": True, "issue_key": issue_key, "status": status}


if __name__ == "__main__":
    print(update_item_status("test_001", "done"))
