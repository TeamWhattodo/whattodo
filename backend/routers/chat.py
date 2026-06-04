from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Any, Optional
import json
import base64

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
    file_name: Optional[str] = None
    file_data: Optional[str] = None  # base64 encoded


def _extract_file_text(file_name: str, file_data: str) -> str:
    raw = base64.b64decode(file_data)
    ext = file_name.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        import fitz
        doc = fitz.open(stream=raw, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    return raw.decode("utf-8", errors="ignore")


def _build_query(req: "ChatRequest") -> str:
    if not req.file_name or not req.file_data:
        return req.query
    try:
        text = _extract_file_text(req.file_name, req.file_data)
        text = text[:8000]
        return f"[첨부 파일: {req.file_name}]\n{text}\n\n{req.query}"
    except Exception as e:
        return f"[첨부 파일 파싱 실패: {e}]\n\n{req.query}"


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
    effective_query = _build_query(req)

    def generate():
        try:
            for event in stream_graph_events(effective_query, thread_id, history or None):
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

        try:
            existing_display, _ = load_session(uid, req.session_id)
            new_display = existing_display + [
                {"role": "user", "content": f"📎 {req.file_name}\n{req.query}" if req.file_name else req.query},
                {"role": "assistant", "content": final_text},
            ]
            history_msgs = [
                HumanMessage(content=m["content"]) if m["role"] == "user"
                else AIMessage(content=m["content"])
                for m in new_display
            ]
            save_session(uid, req.session_id, new_display, history_msgs)
        except Exception as e:
            import logging
            logging.warning(f"세션 저장 실패 (무시): {e}")

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




@router.get("/policy/status")
def get_policy_status():
    from backend.db.store import policy_ingest_status
    return policy_ingest_status


@router.get("/sync/status")
def get_sync_status():
    from sqlalchemy import text
    from backend.db.store import get_session
    with get_session() as db:
        rows = db.execute(text("SELECT source, last_synced_at, status, items_count, error_message FROM sync_log")).fetchall()
    return [
        {
            "source":         r[0],
            "last_synced_at": r[1].isoformat() if r[1] else None,
            "status":         r[2],
            "items_count":    r[3],
            "error_message":  r[4],
        }
        for r in rows
    ]
