"""Gmail 메일 → WorkItem 목록 변환"""
import base64
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from googleapiclient.discovery import build
from backend.google_auth import get_credentials
from backend.models import WorkItem


def fetch_gmail(max_results: int = 20) -> list[WorkItem]:
    creds = get_credentials()
    if not creds:
        return []

    service = build("gmail", "v1", credentials=creds)
    msgs = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q="is:unread")
        .execute()
        .get("messages", [])
    )

    items: list[WorkItem] = []
    for m in msgs:
        detail = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        item = _parse_message(detail)
        if item:
            items.append(item)
    return items


def _parse_message(msg: dict) -> WorkItem | None:
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    subject = headers.get("Subject", "(제목 없음)")
    sender = headers.get("From", "")
    date_str = headers.get("Date", "")

    try:
        created_at = parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        created_at = datetime.utcnow()

    body = _extract_body(msg["payload"])
    raw = f"From: {sender}\nSubject: {subject}\n\n{body[:500]}"

    return WorkItem(
        id=hashlib.md5(msg["id"].encode()).hexdigest(),
        source="gmail",
        raw_content=raw,
        summary=f"[메일] {subject} (from {sender})",
        urgency_level=3,
        action_type="reply",
        from_person=sender,
        created_at=created_at,
        source_id=msg.get("threadId"),
    )


def _extract_body(payload: dict) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""
