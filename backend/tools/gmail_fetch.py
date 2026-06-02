"""Gmail 메일 → WorkItem 목록 변환 + 발송·삭제"""
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from googleapiclient.discovery import build
from backend.google_auth import get_credentials
from backend.models import WorkItem


def fetch_gmail(max_results: int = 20, query: str = "is:unread") -> list[WorkItem]:
    """
    query 예시:
      "is:unread"        → 읽지 않은 메일만
      "is:read"          → 읽은 메일만
      ""                 → 읽은 + 읽지 않은 전체
      "is:unread from:boss@company.com" → 특정 발신자의 읽지 않은 메일
    """
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Gmail 인증이 필요합니다. Google 계정을 먼저 연결해주세요.")

    service = build("gmail", "v1", credentials=creds)
    msgs = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query)
        .execute()
        .get("messages", [])
    )

    if not msgs:
        return []

    def _fetch_detail(msg_id: str) -> dict:
        return service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

    items: list[WorkItem] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_detail, m["id"]): m for m in msgs}
        for future in as_completed(futures):
            try:
                item = _parse_message(future.result())
                if item:
                    items.append(item)
            except Exception:
                pass
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


def send_gmail(to: str, subject: str, body: str, thread_id: str = "") -> dict:
    """Gmail로 이메일을 발송한다. thread_id 제공 시 해당 스레드의 답장으로 전송."""
    creds = get_credentials()
    if not creds or not creds.valid:
        return {"success": False, "error": "Google 계정이 연결되지 않았습니다."}

    service = build("gmail", "v1", credentials=creds)
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body_dict: dict = {"raw": raw}
    if thread_id:
        body_dict["threadId"] = thread_id

    try:
        result = service.users().messages().send(userId="me", body=body_dict).execute()
        return {"success": True, "message_id": result.get("id"), "thread_id": result.get("threadId")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def trash_gmail(message_id: str) -> dict:
    """Gmail 메시지를 휴지통으로 이동한다. message_id: Gmail 메시지 ID."""
    creds = get_credentials()
    if not creds or not creds.valid:
        return {"success": False, "error": "Google 계정이 연결되지 않았습니다."}

    service = build("gmail", "v1", credentials=creds)
    try:
        service.users().messages().trash(userId="me", id=message_id).execute()
        return {"success": True, "message_id": message_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _extract_body(payload: dict) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""
