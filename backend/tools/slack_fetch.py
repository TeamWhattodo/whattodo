import json
from langchain_core.tools import tool
from backend.config import settings


def _client():
    from slack_sdk import WebClient
    return WebClient(token=settings.slack_bot_token)


def _safe(fn):
    try:
        return json.dumps(fn().data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def slack_list_channels(limit: int = 100) -> str:
    """봇이 참여 중인 Slack 채널 목록을 조회합니다. 반환된 채널은 모두 메시지 조회 가능."""
    try:
        result = _client().conversations_list(limit=limit, types="public_channel")
        data = result.data
        data["channels"] = [c for c in data.get("channels", []) if c.get("is_member")]
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def slack_get_channel_history(channel_id: str, limit: int = 50) -> str:
    """Slack 채널 메시지를 조회합니다. channel_id는 반드시 C로 시작하는 ID값 사용 (채널 이름 불가)."""
    if not channel_id.startswith("C"):
        return json.dumps({"ok": False, "error": f"channel_id must start with 'C' (got '{channel_id}'). Call slack_list_channels first to get the id."}, ensure_ascii=False)
    return _safe(lambda: _client().conversations_history(channel=channel_id, limit=limit))


@tool
def slack_get_thread_replies(channel_id: str, thread_ts: str, limit: int = 50) -> str:
    """Slack 스레드 답글을 조회합니다."""
    return _safe(lambda: _client().conversations_replies(channel=channel_id, ts=thread_ts, limit=limit))


@tool
def slack_post_message(channel_id: str, text: str, thread_ts: str = "") -> str:
    """Slack 채널에 메시지를 전송합니다. thread_ts 제공 시 해당 메시지의 스레드 답글로 전송. 반드시 사용자 확인 후 실행."""
    kwargs = {"channel": channel_id, "text": text}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    return _safe(lambda: _client().chat_postMessage(**kwargs))


@tool
def slack_search_messages(query: str, count: int = 20) -> str:
    """Slack 전체 메시지를 키워드로 검색합니다."""
    return _safe(lambda: _client().search_messages(query=query, count=count))


@tool
def fetch_slack_as_items(channel_id: str, limit: int = 30) -> str:
    """Slack 채널 메시지를 WorkItem으로 변환해 TinyDB에 저장하고 목록을 반환합니다.
    channel_id: C로 시작하는 채널 ID. 저장된 item_id로 스레드 조회 및 답장 초안 작성 가능."""
    import hashlib
    from datetime import datetime
    from backend.models import WorkItem
    from backend.tools.storage import save_items

    if not channel_id.startswith("C"):
        return json.dumps({"ok": False, "error": f"channel_id must start with 'C' (got '{channel_id}')"}, ensure_ascii=False)

    try:
        result = _client().conversations_history(channel=channel_id, limit=limit)
        messages = result.data.get("messages", [])
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    items = []
    for msg in messages:
        ts = msg.get("ts", "")
        text = msg.get("text", "")
        user = msg.get("user") or msg.get("username") or "unknown"
        if not text or msg.get("subtype"):  # 시스템 메시지 제외
            continue

        source_id = f"{channel_id}:{ts}"
        item = WorkItem(
            id=hashlib.md5(source_id.encode()).hexdigest(),
            source="slack",
            raw_content=text[:1000],
            summary=f"[Slack] {text[:80]}{'...' if len(text) > 80 else ''}",
            urgency_level=3,
            action_type="reply",
            from_person=user,
            source_id=source_id,
            created_at=datetime.utcfromtimestamp(float(ts)) if ts else datetime.utcnow(),
        )
        items.append(item.model_dump(mode="json"))

    save_items(items)
    return json.dumps({"ok": True, "saved": len(items), "items": items}, ensure_ascii=False, default=str)


SLACK_TOOLS = [
    slack_list_channels,
    slack_get_channel_history,
    slack_get_thread_replies,
    slack_post_message,
    slack_search_messages,
    fetch_slack_as_items,
]
