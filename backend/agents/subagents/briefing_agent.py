from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

BRIEFING_AGENT_LOCAL_TOOLS: list[str] = [
    "score_urgency",
    "classify_items",
    "write_report",
]

BRIEFING_AGENT_MCP_PREFIXES: list[str] = ["slack_", "jira_"]

BRIEFING_AGENT_SYSTEM = """\
당신은 브리핑 전담 에이전트입니다.
사용 가능한 tool: slack_* (Slack 수집), jira_* (Jira 이슈 수집),
                  score_urgency, classify_items, write_report

제약:
- score_urgency는 반드시 fetch 완료 후 실행
- write_report는 반드시 classify 완료 후 실행
- 수집 결과가 0건이면 score/classify 생략 가능
- 소스 연결 실패 시 가능한 소스로만 진행하고 사용자에게 알림

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) + MCP 툴(prefix 매칭) 반환."""
    local_names = set(BRIEFING_AGENT_LOCAL_TOOLS)
    return [
        t for t in all_tools
        if t.name in local_names
        or any(t.name.startswith(p) for p in BRIEFING_AGENT_MCP_PREFIXES)
    ]


_agent = create_agent(
    model=get_llm("fast"),
    tools=_build_tools(load_all_tools()),
    system_prompt=BRIEFING_AGENT_SYSTEM,
)


async def _run_async(user_input: str) -> tuple[str, bool]:
    result = await _agent.ainvoke({"messages": [HumanMessage(content=user_input)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    has_write = any(getattr(m, "name", "") == "write_report" for m in messages)
    return output_text, has_write


def briefing_agent_node(state: WhatToDoState) -> WhatToDoState:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        **state,
        "results": {**state.get("results", {}), "briefing": {"text": text}},
        "has_write_output": state.get("has_write_output", False) or has_write,
    }
