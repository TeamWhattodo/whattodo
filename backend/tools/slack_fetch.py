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
def slack_post_message(channel_id: str, text: str) -> str:
    """Slack 채널에 메시지를 전송합니다. 반드시 사용자 확인 후 실행."""
    return _safe(lambda: _client().chat_postMessage(channel=channel_id, text=text))


@tool
def slack_search_messages(query: str, count: int = 20) -> str:
    """Slack 전체 메시지를 키워드로 검색합니다."""
    return _safe(lambda: _client().search_messages(query=query, count=count))


SLACK_TOOLS = [
    slack_list_channels,
    slack_get_channel_history,
    slack_get_thread_replies,
    slack_post_message,
    slack_search_messages,
]
