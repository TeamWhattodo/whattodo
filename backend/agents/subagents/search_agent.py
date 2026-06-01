from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

SEARCH_AGENT_LOCAL_TOOLS: list[str] = [
    "search_past_items",
    "search_company_docs",
    "get_item_thread",
    "fetch_gmail",
    "fetch_calendar",
]

SEARCH_AGENT_MCP_TOOLS: list[str] = [
    "slack_search_messages",
    "jira_search",
    "API-post-search",
    "API-get-block-children",
]

SEARCH_AGENT_SYSTEM = """\
당신은 조회 전담 에이전트입니다.
항상 한국어로만 답변하세요.

━━ 툴 선택 기준 ━━

- 메일·이메일 관련 질문 → fetch_gmail(max_results=20) 호출
- 캘린더·일정 관련 질문 → fetch_calendar(days=7) 호출
- 사내 규정·정책·한도 질문 → search_company_docs 우선 사용
- 과거 처리한 업무 항목 → search_past_items 우선 사용
- 특정 항목의 전체 스레드·맥락 조회 → get_item_thread(item_id, source)
- Notion 내용 조회 → API-post-search 후 API-get-block-children
- Slack 메시지 검색 → slack_search_messages
- Jira 이슈 검색 → jira_search

절대 툴 호출 없이 메일·일정 내용을 지어내지 마세요.
두 결과가 모두 필요하면 병렬 호출 가능합니다.\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) + MCP 툴(이름 매칭) 반환."""
    allowed = set(SEARCH_AGENT_LOCAL_TOOLS) | set(SEARCH_AGENT_MCP_TOOLS)
    return [t for t in all_tools if t.name in allowed]


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=SEARCH_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(user_input: str) -> tuple[str, bool]:
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=user_input)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    return output_text, False  # search는 write 없음


def search_agent_node(state: WhatToDoState) -> dict:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        "results": {"search": {"text": text}},
        "has_write_output": has_write,
    }
