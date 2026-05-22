from backend.tools.storage import update_item_status as _update_status


def update_item_status(item_id: str, status: str) -> dict:
    """
    WorkItem 상태를 변경한다.
    status: done | snoozed | pending
    """
    return _update_status(item_id, status)


def create_calendar_block(title: str, start: str, end: str) -> dict:
    """캘린더 블록을 생성한다. (Week 2: Google Calendar API 연결)"""
    # TODO (#2): Google Calendar API 연결
    return {"success": True, "event_id": f"mock_{title[:10]}", "title": title, "start": start, "end": end}


def update_jira_issue(issue_key: str, status: str) -> dict:
    """Jira 이슈 상태를 변경한다. (Phase 2: Jira API 연결)"""
    # TODO (#2): Jira API 연결
    return {"success": True, "issue_key": issue_key, "status": status}


if __name__ == "__main__":
    print(update_item_status("test_001", "done"))
