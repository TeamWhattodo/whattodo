import json
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

SESSION_ROOT = Path("data/sessions")


def _user_dir(user_id: str) -> Path:
    return SESSION_ROOT / str(user_id)


def _safe_session_id(session_id: str) -> str:
    if "/" in session_id or "\\" in session_id or ".." in session_id:
        raise ValueError(f"invalid session_id: {session_id!r}")
    return session_id


def save_session(user_id: str, session_id: str,
                 display_messages: list[dict],
                 langchain_history: list[BaseMessage]) -> None:
    simple_history = []
    for msg in langchain_history:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            simple_history.append({"type": "human", "content": content})
        elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            simple_history.append({"type": "ai", "content": msg.content})

    path = _user_dir(user_id) / f"{_safe_session_id(session_id)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_name = None
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing_name = json.load(f).get("name")
        except Exception:
            pass

    data: dict = {"display": display_messages, "history": simple_history}
    if existing_name:
        data["name"] = existing_name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def rename_session(user_id: str, session_id: str, name: str) -> None:
    path = _user_dir(user_id) / f"{_safe_session_id(session_id)}.json"
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["name"] = name.strip() or "새 대화"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session(user_id: str, session_id: str) -> tuple[list[dict], list[BaseMessage]]:
    path = _user_dir(user_id) / f"{_safe_session_id(session_id)}.json"
    if not path.exists():
        return [], []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    history: list[BaseMessage] = []
    for item in data.get("history", []):
        if item["type"] == "human":
            history.append(HumanMessage(content=item["content"]))
        elif item["type"] == "ai":
            history.append(AIMessage(content=item["content"]))
    return data.get("display", []), history


def list_sessions(user_id: str) -> list[dict]:
    base = _user_dir(user_id)
    if not base.exists():
        return []
    sessions = []
    for path in sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            display = data.get("display", [])
            saved_name = data.get("name")
            if not saved_name:
                first_user = next(
                    (m["content"] for m in display if m["role"] == "user"), None
                )
                saved_name = (first_user[:20] + "...") if first_user and len(first_user) > 20 else (first_user or "새 대화")
            sessions.append({"id": path.stem, "name": saved_name})
        except Exception:
            continue
    return sessions


def delete_session(user_id: str, session_id: str) -> None:
    path = _user_dir(user_id) / f"{_safe_session_id(session_id)}.json"
    if path.exists():
        path.unlink()
