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
    "search_calendar_events",
    "fetch_calendar",
    "list_notion_pages",
]

SEARCH_AGENT_MCP_TOOLS: list[str] = [
    "slack_search_messages",
    "jira_search",
    "API-post-search",
    "API-get-block-children",
]

SEARCH_AGENT_SYSTEM = """\
당신은 조회 전담 에이전트입니다.

## 툴 선택 기준
- 특정 item_id(32자 hex)의 내용·스레드 요청 → get_item_thread(item_id, source) 사용
- 특정 메일·메시지 내용 조회 → search_past_items로 항목 찾은 뒤 get_item_thread로 상세 내용 반환
- 사내 규정 질문 → search_company_docs 우선 사용
- 과거 업무 항목 검색 → search_past_items 사용
- 캘린더·일정 관련 질문 → search_calendar_events 또는 fetch_calendar 사용

## 검색 방법
- search_past_items의 query에는 사용자 문장 전체가 아닌 **핵심 키워드만** 입력
  예) "신현섭 · 테스트 메시지 내용 보고싶어" → query="테스트 메시지" 또는 query="신현섭"
- 첫 검색에서 안 나오면 query를 더 짧게 줄여서 재시도
- source 파라미터로 범위 좁히기 가능 (gmail·slack·jira)

## 출력 규칙
- 툴이 반환한 실제 데이터만 출력. 데이터를 만들어내거나 예시를 사용하지 말 것.
- get_item_thread 결과가 있으면 발신자·제목·본문을 정리해서 출력
- 결과가 없으면 "해당 항목을 찾을 수 없습니다"로 출력\
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
