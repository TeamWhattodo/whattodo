import asyncio
import json
import threading
from pathlib import Path
from typing import Generator

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, BaseMessage

from backend.agents.llm_client import get_llm
from backend.agents.prompts import SYSTEM_PROMPT
from backend.mcp_client import load_mcp_tools, MCP_SERVER_CONFIG

# ── 후처리 툴 임포트 ──────────────────────────────────────────────────────────
from backend.tools.scoring import score_urgency as _score_urgency
from backend.tools.classify import classify_items as _classify, filter_items as _filter
from backend.tools.write_report import write_report as _write_report
from backend.tools.write_draft import write_draft as _write_draft
from backend.tools.update_status import update_item_status as _update_status
from backend.tools.search_items import search_past_items as _search
from backend.tools.policy_search import search_company_docs as _search_docs


# ── 후처리 @tool 래퍼 ─────────────────────────────────────────────────────────

@tool
def score_urgency(items: list) -> str:
    """WorkItem 목록에 긴급도(1~5)를 계산합니다. LLM 미사용."""
    return json.dumps(_score_urgency(items), ensure_ascii=False, default=str)

@tool
def classify_items(items: list) -> str:
    """항목에 액션 타입(reply/approve/review/fyi/none)과 요약을 부여합니다. LLM Fast 티어 사용."""
    return json.dumps(_classify(items), ensure_ascii=False, default=str)

@tool
def filter_items(items: list, min_urgency: int = 3) -> str:
    """urgency_level >= min_urgency 인 항목만 필터링합니다."""
    return json.dumps(_filter(items, min_urgency), ensure_ascii=False, default=str)

@tool
def write_report(report_type: str, data: str) -> str:
    """업무 보고서를 작성합니다. report_type: briefing | daily_summary | kpi_weekly | billing. data: JSON 문자열."""
    try:
        parsed = json.loads(data)
    except Exception:
        parsed = data
    return json.dumps(_write_report(report_type, parsed), ensure_ascii=False, default=str)

@tool
def write_draft(item_id: str, tone: str = "formal") -> str:
    """item_id로 항목을 조회해 답장 초안을 생성합니다. tone: formal | casual."""
    return json.dumps(_write_draft(item_id, tone), ensure_ascii=False, default=str)

@tool
def update_item_status(item_id: str, status: str) -> str:
    """항목 상태를 변경합니다. status: done | snoozed | pending."""
    return json.dumps(_update_status(item_id, status), ensure_ascii=False, default=str)

@tool
def search_past_items(query: str = "", status: str = "", source: str = "") -> str:
    """저장된 WorkItem을 검색합니다. query: 키워드, status: done|pending|snoozed, source: gmail|slack|jira."""
    return json.dumps(
        _search(query=query, status=status or None, source=source or None),
        ensure_ascii=False, default=str
    )

@tool
def search_company_docs(query: str, top_k: int = 3) -> str:
    """사내 규정·문서에서 query와 관련된 내용을 검색합니다. 규정 조회, 정산 검증, 미팅 준비 시 사용."""
    return _search_docs(query, top_k)

@tool
def process_expense_report(image_paths: list[str]) -> str:
    """업로드된 영수증 이미지를 분석해 경비정산서(엑셀·PDF)를 작성합니다. image_paths: 이미지 파일 경로 목록."""
    from backend.tools.receipt import parse_receipt
    from backend.tools.expense import build_expense_report
    items  = parse_receipt(image_paths)
    report = build_expense_report(items)
    return json.dumps({
        "total_amount": report["total_amount"],
        "items":        report["items"],
        "xlsx_path":    report["xlsx_path"],
        "pdf_path":     report["pdf_path"],
    }, ensure_ascii=False, default=str)


# ── 영구 백그라운드 이벤트 루프 (MCP 세션 유지용) ─────────────────────────────

_bg_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
threading.Thread(target=_bg_loop.run_forever, daemon=True).start()


def _run(coro):
    """백그라운드 루프에서 코루틴을 실행하고 결과를 반환한다."""
    return asyncio.run_coroutine_threadsafe(coro, _bg_loop).result()


def _load_mcp_tools_sync() -> list:
    """MCP 서버 툴을 백그라운드 루프에서 로드한다. 세션은 루프가 살아 있는 한 유지된다."""
    if not MCP_SERVER_CONFIG:
        return []
    try:
        return _run(load_mcp_tools())
    except Exception as e:
        print(f"[MCP] 툴 로드 중 오류 발생, MCP 없이 시작합니다: {e}")
        return []


# ── 에이전트 구성 ──────────────────────────────────────────────────────────────

PROCESSING_TOOLS = [
    score_urgency,
    classify_items,
    filter_items,
    write_report,
    write_draft,
    update_item_status,
    search_past_items,
    search_company_docs,
    process_expense_report,
]

TOOLS = PROCESSING_TOOLS + _load_mcp_tools_sync()

agent = create_agent(
    model=get_llm("smart"),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


async def _run_agent_async(
    user_message: str,
    history: list[BaseMessage],
) -> tuple[str, list[BaseMessage]]:
    messages = history + [HumanMessage(content=user_message)]
    result = await agent.ainvoke({"messages": messages})
    output_messages: list[BaseMessage] = result["messages"]
    output_text = output_messages[-1].content if output_messages else ""
    return output_text, output_messages


def run_agent(
    user_message: str,
    history: list[BaseMessage],
    on_step=None,
) -> tuple[str, list[BaseMessage]]:
    return _run(_run_agent_async(user_message, history))


async def _stream_agent_async(
    user_message: str,
    history: list[BaseMessage],
) -> list[dict]:
    messages = history + [HumanMessage(content=user_message)]
    accumulated: list[BaseMessage] = list(messages)
    events: list[dict] = []

    async for chunk in agent.astream({"messages": messages}):
        for node_state in chunk.values():
            for msg in node_state.get("messages", []):
                accumulated.append(msg)
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        events.append({"type": "tool_call", "tool": tc["name"], "args": tc.get("args", {})})
                elif hasattr(msg, "name") and msg.name:
                    content = msg.content
                    if isinstance(content, list):
                        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                    events.append({"type": "tool_result", "tool": msg.name, "content": str(content)})

    final_text = accumulated[-1].content if accumulated else ""
    if isinstance(final_text, list):
        final_text = " ".join(b.get("text", "") for b in final_text if isinstance(b, dict))
    events.append({"type": "done", "text": final_text, "history": accumulated})
    return events


def stream_agent(
    user_message: str,
    history: list[BaseMessage],
) -> Generator[dict, None, None]:
    yield from _run(_stream_agent_async(user_message, history))


SESSION_DIR = Path("data/sessions")


def save_session(session_id: str, display_messages: list[dict], langchain_history: list[BaseMessage]) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    simple_history = []
    for msg in langchain_history:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            simple_history.append({"type": "human", "content": content})
        elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            simple_history.append({"type": "ai", "content": msg.content})

    path = SESSION_DIR / f"{session_id}.json"
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


def rename_session(session_id: str, name: str) -> None:
    path = SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["name"] = name.strip() or "새 대화"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> tuple[list[dict], list[BaseMessage]]:
    path = SESSION_DIR / f"{session_id}.json"
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


def list_sessions() -> list[dict]:
    if not SESSION_DIR.exists():
        return []
    sessions = []
    for path in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
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


def delete_session(session_id: str) -> None:
    path = SESSION_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


if __name__ == "__main__":
    answer, hist = run_agent("긴급한 업무 정리해줘", history=[])
    print(answer)
