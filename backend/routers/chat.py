from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Any
import json

from backend.agents.assistant_agent import (
    stream_agent, save_session, load_session,
    list_sessions, delete_session, rename_session
)
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    session_id: str
    chat_history: List[Any] = []

class SessionRenameRequest(BaseModel):
    name: str

def serialize_history(history):
    result = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            result.append({"type": "human", "content": msg.content if isinstance(msg.content, str) else str(msg.content)})
        elif isinstance(msg, AIMessage):
            if isinstance(msg.content, str) and msg.content.strip():
                result.append({"type": "ai", "content": msg.content})
    return result

def deserialize_history(history_data):
    history = []
    for item in history_data:
        if isinstance(item, dict):
            if item.get("type") == "human":
                history.append(HumanMessage(content=item["content"]))
            elif item.get("type") == "ai":
                history.append(AIMessage(content=item["content"]))
    return history

@router.post("/chat")
async def chat_stream(req: ChatRequest):
    history = deserialize_history(req.chat_history)
    def generate():
        for event in stream_agent(req.query, history):
            try:
                if event.get("type") == "done" and "history" in event:
                    event = {**event, "history": serialize_history(event["history"])}
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

@router.get("/sessions")
def get_sessions():
    return list_sessions()

@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    display, history = load_session(session_id)
    return {"messages": display, "chat_history": serialize_history(history)}

@router.post("/sessions/{session_id}")
def post_save_session(session_id: str, req: ChatRequest):
    history = deserialize_history(req.chat_history)
    save_session(session_id, [], history)
    return {"ok": True}

@router.patch("/sessions/{session_id}")
def patch_session(session_id: str, req: SessionRenameRequest):
    rename_session(session_id, req.name)
    return {"ok": True}

@router.delete("/sessions/{session_id}")
def del_session(session_id: str):
    delete_session(session_id)
    return {"ok": True}

@router.get("/integrations")
def get_integrations():
    from backend.mcp_client import MCP_SERVER_CONFIG
    return {
        "slack": "slack" in MCP_SERVER_CONFIG,
        "jira":  "jira"  in MCP_SERVER_CONFIG,
    }