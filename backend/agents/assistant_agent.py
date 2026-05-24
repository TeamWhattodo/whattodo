import json
from pathlib import Path
from typing import Generator
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, BaseMessage

from backend.agents.llm_client import get_llm
from backend.agents.prompts import SYSTEM_PROMPT

# ── 기반 함수 임포트 ─────────────────────────────────────────────────────────
from backend.tools.fetch import (
    fetch_emails as _fetch_emails,
    fetch_slack_messages as _fetch_slack,
    fetch_calendar_events as _fetch_calendar,
    fetch_jira_issues as _fetch_jira,
)
from backend.tools.scoring import score_urgency as _score_urgency
from backend.tools.classify import classify_items as _classify, filter_items as _filter
from backend.tools.write_report import write_report as _write_report
from backend.tools.write_draft import write_draft as _write_draft
from backend.tools.update_status import update_item_status as _update_status
from backend.tools.search_items import search_past_items as _search
from backend.tools.policy_search import search_company_docs as _search_docs


# ── LangChain @tool 래퍼 ──────────────────────────────────────────────────────

@tool
def fetch_emails(since_hours: int = 24, max_count: int = 50) -> str:
    """Gmail에서 미읽음 이메일을 수집합니다. since_hours: 몇 시간 전부터."""
    return json.dumps(_fetch_emails(since_hours, max_count), ensure_ascii=False, default=str)

@tool
def fetch_slack_messages(since_hours: int = 24, mention_only: bool = True) -> str:
    """Slack 멘션·DM을 수집합니다."""
    return json.dumps(_fetch_slack(since_hours, mention_only), ensure_ascii=False, default=str)

@tool
def fetch_calendar_events(date_range: int = 3) -> str:
    """오늘 기준 date_range일 내 캘린더 일정을 수집합니다."""
    return json.dumps(_fetch_calendar(date_range), ensure_ascii=False, default=str)

@tool
def fetch_jira_issues(due_within_days: int = 7) -> str:
    """Jira에서 나에게 할당된 이슈를 수집합니다."""
    return json.dumps(_fetch_jira(due_within_days), ensure_ascii=False, default=str)

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


# ── 에이전트 구성 ──────────────────────────────────────────────────────────────

TOOLS = [
    fetch_emails,
    fetch_slack_messages,
    fetch_calendar_events,
    fetch_jira_issues,
    score_urgency,
    classify_items,
    filter_items,
    write_report,
    write_draft,
    update_item_status,
    search_past_items,
    search_company_docs,
]

agent = create_agent(
    model=get_llm("smart"),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


def run_agent(
    user_message: str,
    history: list[BaseMessage],
    on_step=None,       # Week 3: Streamlit 단계별 렌더링 콜백 (현재 미사용)
) -> tuple[str, list[BaseMessage]]:
    """
    LangChain 에이전트 실행.
    history: LangChain Message 객체 리스트 (HumanMessage, AIMessage)
    반환: (최종 답변 텍스트, 업데이트된 history)
    """
    messages = history + [HumanMessage(content=user_message)]
    result = agent.invoke({"messages": messages})
    output_messages: list[BaseMessage] = result["messages"]
    output_text = output_messages[-1].content if output_messages else ""
    return output_text, output_messages


def stream_agent(
    user_message: str,
    history: list[BaseMessage],
) -> Generator[dict, None, None]:
    """
    에이전트 실행을 step별로 yield한다.
    {"type": "tool_call", "tool": str, "args": dict}
    {"type": "tool_result", "tool": str, "content": str}
    {"type": "text_chunk", "text": str}          ← 스트리밍 토큰
    {"type": "done", "text": str, "history": list[BaseMessage]}
    """
    messages = history + [HumanMessage(content=user_message)]
    all_messages: list[BaseMessage] = list(messages)
    current_ai_chunk: AIMessageChunk | None = None
    seen_tools: set[str] = set()

    for chunk, _ in agent.stream({"messages": messages}, stream_mode="messages"):
        if isinstance(chunk, AIMessageChunk):
            current_ai_chunk = chunk if current_ai_chunk is None else current_ai_chunk + chunk

            # 도구 호출 이벤트 (도구명 당 1회만 emit)
            for tc in (chunk.tool_call_chunks or []):
                name = tc.get("name", "")
                if name and name not in seen_tools:
                    seen_tools.add(name)
                    yield {"type": "tool_call", "tool": name, "args": {}}

            # 텍스트 토큰 스트리밍
            if chunk.content and isinstance(chunk.content, str):
                yield {"type": "text_chunk", "text": chunk.content}

        else:
            # AI 메시지 누적 완료
            if current_ai_chunk is not None:
                all_messages.append(current_ai_chunk)
                current_ai_chunk = None
                seen_tools = set()
            all_messages.append(chunk)

            # 도구 결과 이벤트
            if hasattr(chunk, "name") and chunk.name:
                content = chunk.content
                if isinstance(content, list):
                    content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                yield {"type": "tool_result", "tool": chunk.name, "content": str(content)}

    if current_ai_chunk is not None:
        all_messages.append(current_ai_chunk)

    last = all_messages[-1] if all_messages else None
    final_text = ""
    if last:
        c = getattr(last, "content", "")
        final_text = c if isinstance(c, str) else str(c)

    yield {"type": "done", "text": final_text, "history": all_messages}


SESSION_DIR = Path("data/sessions")


def save_session(session_id: str, display_messages: list[dict], langchain_history: list[BaseMessage]) -> None:
    """대화 히스토리를 JSON 파일로 저장."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    simple_history = []
    for msg in langchain_history:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            simple_history.append({"type": "human", "content": content})
        elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            simple_history.append({"type": "ai", "content": msg.content})

    path = SESSION_DIR / f"{session_id}.json"
    # 기존 name 필드 유지
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
    """세션 제목 변경."""
    path = SESSION_DIR / f"{session_id}.json"
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["name"] = name.strip() or "새 대화"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> tuple[list[dict], list[BaseMessage]]:
    """JSON 파일에서 대화 히스토리를 불러옴."""
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
    """저장된 세션 목록을 최신순으로 반환. [{id, name, mtime}]"""
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
    """세션 파일 삭제."""
    path = SESSION_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


if __name__ == "__main__":
    answer, hist = run_agent("긴급한 업무 정리해줘", history=[])
    print(answer)
