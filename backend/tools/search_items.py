from backend.tools.storage import search_items as _search, get_item_by_id


def search_past_items(query: str = "", date_range: str = "7d", status: str = None, source: str = None) -> list[dict]:
    """
    저장된 WorkItem을 조건으로 검색한다.
    date_range: "today" | "7d" | "30d" (현재 구현은 date_range 무시)
    status: "done" | "pending" | "snoozed" | None (전체)
    """
    # TODO (#5): date_range 필터링 구현
    return _search(query=query, status=status, source=source)


def get_item_thread(item_id: str, source: str) -> list[dict]:
    """
    특정 항목의 스레드 전체를 조회한다.
    - gmail: source_id(threadId)로 Gmail 스레드 전체 메시지 반환
    - slack: source_id(channel_id:thread_ts)로 Slack 스레드 답글 반환
    - 그 외: 저장된 item 단건 반환
    """
    item = get_item_by_id(item_id)
    if not item:
        return [{"item_id": item_id, "error": "항목을 찾을 수 없습니다."}]

    source_id = item.get("source_id")

    if source == "gmail":
        return _fetch_gmail_thread(item, source_id)
    if source == "slack":
        return _fetch_slack_thread(item, source_id)

    # calendar / jira / notion — 저장된 item 반환
    return [{"item_id": item_id, "source": source, "content": item.get("raw_content", ""), "item": item}]


def _fetch_gmail_thread(item: dict, thread_id: str | None) -> list[dict]:
    if not thread_id:
        return [{"item_id": item["id"], "source": "gmail", "content": item.get("raw_content", ""), "note": "threadId 미저장 — Gmail 재수집 후 사용 가능"}]

    import base64
    from googleapiclient.discovery import build
    from backend.google_auth import get_credentials

    creds = get_credentials()
    if not creds or not creds.valid:
        return [{"item_id": item["id"], "source": "gmail", "content": item.get("raw_content", ""), "note": "Google 미인증"}]

    service = build("gmail", "v1", credentials=creds)
    try:
        thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    except Exception as e:
        return [{"item_id": item["id"], "source": "gmail", "error": str(e)}]

    messages = []
    for msg in thread.get("messages", []):
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = _extract_gmail_body(msg["payload"])
        messages.append({
            "message_id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": body[:1000],
        })
    return messages


def _fetch_slack_thread(item: dict, source_id: str | None) -> list[dict]:
    if not source_id or ":" not in source_id:
        return [{"item_id": item["id"], "source": "slack", "content": item.get("raw_content", ""), "note": "channel_id:thread_ts 미저장"}]

    channel_id, thread_ts = source_id.split(":", 1)
    try:
        from backend.tools.slack_fetch import _client
        result = _client().conversations_replies(channel=channel_id, ts=thread_ts, limit=50)
        msgs = result.data.get("messages", [])
        return [
            {
                "message_id": m.get("ts"),
                "from": m.get("user", "unknown"),
                "text": m.get("text", ""),
                "ts": m.get("ts"),
            }
            for m in msgs
        ]
    except Exception as e:
        return [{"item_id": item["id"], "source": "slack", "error": str(e)}]


def _extract_gmail_body(payload: dict) -> str:
    import base64
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


if __name__ == "__main__":
    print(search_past_items(status="pending"))
