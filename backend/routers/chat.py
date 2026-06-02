from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Any
import json

from backend.agents.graph import stream_graph_events, get_graph_state
from backend.agents.sessions import (
    save_session, load_session, list_sessions, delete_session, rename_session,
)
from backend.auth.deps import get_current_user
from backend.auth.models import User
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: str
    chat_history: List[Any] = []


class SessionRenameRequest(BaseModel):
    name: str


def _deserialize_history(history_data: list) -> list:
    result = []
    for item in history_data:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "human":
            result.append(HumanMessage(content=item["content"]))
        elif item.get("type") == "ai":
            result.append(AIMessage(content=item["content"]))
    return result


def _translate_event(event: dict) -> dict | None:
    """LangGraph astream_events v2 → 프론트 SSE 포맷 변환."""
    etype = event.get("event", "")
    name = event.get("name", "")
    if etype == "on_tool_start":
        return {"type": "tool_call", "tool": name}
    if etype == "on_tool_end":
        return {"type": "tool_result", "tool": name}
    return None


@router.post("/chat")
async def chat_stream(req: ChatRequest, user: User = Depends(get_current_user)):
    history = _deserialize_history(req.chat_history)
    uid = str(user.id)
    thread_id = f"{uid}:{req.session_id}"

    def generate():
        try:
            for event in stream_graph_events(req.query, thread_id, history or None):
                translated = _translate_event(event)
                if translated:
                    yield f"data: {json.dumps(translated, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"
            return

        try:
            state = get_graph_state(thread_id)
            msgs = state.values.get("messages", [])
            last_ai = next(
                (m for m in reversed(msgs)
                 if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip()),
                None,
            )
            final_text = last_ai.content if last_ai else ""
        except Exception:
            final_text = ""

        existing_display, _ = load_session(uid, req.session_id)
        new_display = existing_display + [
            {"role": "user", "content": req.query},
            {"role": "assistant", "content": final_text},
        ]
        history_msgs = [
            HumanMessage(content=m["content"]) if m["role"] == "user"
            else AIMessage(content=m["content"])
            for m in new_display
        ]
        save_session(uid, req.session_id, new_display, history_msgs)

        done_payload = {"type": "done", "text": final_text}
        yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions")
def get_sessions(user: User = Depends(get_current_user)):
    return list_sessions(str(user.id))


@router.get("/sessions/{session_id}")
def get_session(session_id: str, user: User = Depends(get_current_user)):
    display, history = load_session(str(user.id), session_id)
    history_data = []
    for m in history:
        if isinstance(m, HumanMessage):
            history_data.append({"type": "human", "content": m.content})
        elif isinstance(m, AIMessage):
            history_data.append({"type": "ai", "content": m.content})
    return {"messages": display, "chat_history": history_data}


@router.patch("/sessions/{session_id}")
def patch_session(session_id: str, req: SessionRenameRequest,
                  user: User = Depends(get_current_user)):
    rename_session(str(user.id), session_id, req.name)
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def del_session(session_id: str, user: User = Depends(get_current_user)):
    delete_session(str(user.id), session_id)
    return {"ok": True}


@router.get("/integrations")
def get_integrations():
    from backend.config import settings
    return {
        "slack": bool(settings.slack_bot_token),
        "jira":  bool(settings.jira_api_token),
        "gmail": bool(settings.gmail_client_id),
    }
