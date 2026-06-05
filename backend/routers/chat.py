import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Any, Optional
import json
import base64

OUTPUTS_DIR = Path("outputs")

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


IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
IMAGE_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "gif": "image/gif", "webp": "image/webp"}


def _extract_file_text(file_name: str, file_data: str) -> str:
    raw = base64.b64decode(file_data)
    ext = file_name.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        import fitz
        doc = fitz.open(stream=raw, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    return raw.decode("utf-8", errors="ignore")


def _extract_files(text: str) -> list[dict]:
    paths = re.findall(r"outputs/[\w\-\.가-힣]+\.(?:pdf|xlsx|csv|txt)", text)
    result = []
    for p in dict.fromkeys(paths):
        fp = OUTPUTS_DIR / Path(p).name
        if fp.exists():
            result.append({"name": fp.name, "url": f"/api/files/{fp.name}"})
    return result


def _build_query(req: "ChatRequest") -> "str | list":
    if not req.file_name or not req.file_data:
        return req.query
    ext = req.file_name.rsplit(".", 1)[-1].lower()
    if ext in IMAGE_EXTS:
        mime = IMAGE_MIME.get(ext, "image/jpeg")
        return [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{req.file_data}"}},
            {"type": "text", "text": req.query},
        ]
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
    import asyncio, functools
    history = _deserialize_history(req.chat_history)
    uid = str(user.id)
    thread_id = f"{uid}:{req.session_id}"
    loop = asyncio.get_event_loop()
    effective_query = await loop.run_in_executor(None, functools.partial(_build_query, req))

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

        files = _extract_files(final_text)
        done_payload = {"type": "done", "text": final_text, "files": files}
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
    from backend.db.store import policy_ingest_status, get_policy_list
    status = policy_ingest_status.copy()
    
    # 실제 존재하는 파일 목록을 조회하여 files 배열 업데이트
    file_list = get_policy_list()
    status["files"] = [f["name"] for f in file_list]
    
    # 현재 실행 중이 아니라면 완료 상태 보정
    if status["status"] != "running":
        status["done_files"] = [f["name"] for f in file_list if f["embedded"]]
        if len(file_list) > 0 and len(status["done_files"]) == len(file_list):
            status["status"] = "done"
        elif len(file_list) > 0:
            status["status"] = "idle"
            
    return status


@router.get("/policy/list")
def get_policies(user: User = Depends(get_current_user)):
    from backend.db.store import get_policy_list
    return get_policy_list()


from fastapi import UploadFile, File
import shutil

@router.post("/policy/upload")
async def upload_policy(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    filename_lower = file.filename.lower()
    print(f"[DEBUG] Uploaded file: {file.filename}, lower: {filename_lower}")
    if not filename_lower.endswith((".pdf", ".hwp", ".hwpx", ".docx", ".doc")):
        print(f"[DEBUG] Rejected file: {file.filename}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")
    
    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = policy_dir / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"ok": True, "filename": file.filename}

@router.post("/policy/ingest/{filename}")
async def ingest_policy(filename: str, user: User = Depends(get_current_user)):
    from backend.db.store import policy_ingest_status, _run_ingest_policy_async
    import asyncio
    if policy_ingest_status["status"] == "running":
        return {"ok": True, "filename": filename}
    asyncio.create_task(_run_ingest_policy_async(filename))
    return {"ok": True, "filename": filename}


@router.delete("/policy/{filename}")
def delete_policy(filename: str, user: User = Depends(get_current_user)):
    from backend.db.store import delete_policy_file
    try:
        delete_policy_file(filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}

@router.get("/policy/files/{filename}")
def download_policy_file(filename: str, user: User = Depends(get_current_user)):
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명")
    policy_dir = Path(__file__).parent.parent.parent / "docs" / "policy"
    path = policy_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일 없음")
    return FileResponse(path, filename=filename, media_type="application/pdf")


@router.get("/files/{filename}")
def download_file(filename: str, user: User = Depends(get_current_user)):
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명")
    path = OUTPUTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일 없음")
    return FileResponse(path, filename=filename)


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
