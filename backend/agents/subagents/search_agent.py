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
]

SEARCH_AGENT_MCP_TOOLS: list[str] = [
    "slack_search_messages",
    "jira_search",
    "API-post-search",
    "API-get-block-children",
]

SEARCH_AGENT_SYSTEM = """\
당신은 조회 전담 에이전트입니다.
사용 가능한 tool: search_past_items, search_company_docs, get_item_thread,
                  slack_search_messages, jira_search,
                  API-post-search, API-get-block-children

제약:
- 사내 규정 질문은 search_company_docs 우선 사용
- 과거 항목 질문은 search_past_items 우선 사용
- 두 결과가 모두 필요하면 병렬 호출 가능

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.\
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
