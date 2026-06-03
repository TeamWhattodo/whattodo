from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from sqlalchemy import text

from backend.db.store import get_session


def save_session(session_id: str, display_messages: list[dict], langchain_history: list[BaseMessage]) -> None:
    simple_history = []
    for msg in langchain_history:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            simple_history.append({"type": "human", "content": content})
        elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            simple_history.append({"type": "ai", "content": msg.content})

    import json as _json
    with get_session() as db:
        db.execute(text("""
            INSERT INTO sessions (session_id, display_messages, history, created_at, updated_at)
            VALUES (:sid, CAST(:display AS jsonb), CAST(:history AS jsonb), :now, :now)
            ON CONFLICT (session_id) DO UPDATE
            SET display_messages = CAST(:display AS jsonb),
                history          = CAST(:history AS jsonb),
                updated_at       = :now
        """), {
            "sid":     session_id,
            "display": _json.dumps(display_messages, ensure_ascii=False),
            "history": _json.dumps(simple_history, ensure_ascii=False),
            "now":     datetime.now(timezone.utc),
        })


def rename_session(session_id: str, name: str) -> None:
    with get_session() as db:
        db.execute(text("""
            UPDATE sessions SET name = :name, updated_at = :now WHERE session_id = :sid
        """), {"sid": session_id, "name": name.strip() or "새 대화", "now": datetime.now(timezone.utc)})


def load_session(session_id: str) -> tuple[list[dict], list[BaseMessage]]:
    with get_session() as db:
        row = db.execute(
            text("SELECT display_messages, history FROM sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()

    if not row:
        return [], []

    history: list[BaseMessage] = []
    for item in (row[1] or []):
        if item["type"] == "human":
            history.append(HumanMessage(content=item["content"]))
        elif item["type"] == "ai":
            history.append(AIMessage(content=item["content"]))
    return row[0] or [], history


def list_sessions() -> list[dict]:
    with get_session() as db:
        rows = db.execute(text("""
            SELECT session_id, name, display_messages
            FROM sessions
            ORDER BY updated_at DESC
        """)).fetchall()

    sessions = []
    for session_id, name, display in rows:
        if not name:
            first_user = next(
                (m["content"] for m in (display or []) if m.get("role") == "user"), None
            )
            name = (first_user[:20] + "...") if first_user and len(first_user) > 20 else (first_user or "새 대화")
        sessions.append({"id": session_id, "name": name})
    return sessions


def delete_session(session_id: str) -> None:
    with get_session() as db:
        db.execute(text("DELETE FROM sessions WHERE session_id = :sid"), {"sid": session_id})
