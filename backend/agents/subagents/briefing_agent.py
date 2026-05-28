from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

BRIEFING_AGENT_LOCAL_TOOLS: list[str] = []

BRIEFING_AGENT_MCP_PREFIXES: list[str] = ["slack_", "jira_", "API-"]

BRIEFING_AGENT_SYSTEM = """\
당신은 브리핑 전담 에이전트입니다. 아래 순서대로 데이터를 수집한 뒤 정리합니다.

━━ 수집 단계 (이 툴만 사용) ━━

[Slack]
① slack_list_channels(limit=100) 호출
② 응답에서 is_member=true 인 채널만 선택 (is_member=false 채널은 건너뜀)
③ 선택된 채널의 id 값(C로 시작하는 문자열)으로만 slack_get_channel_history 호출
   예: slack_get_channel_history(channel_id="C0AJ7P7G03E", limit=50)
   절대 금지: channel_id에 채널 이름(kosa-team, general 등) 사용

[Jira]
① jira_search(jql="statusCategory not in (Done) ORDER BY updated DESC", limit=20)

[Notion]
① API-post-search(query="") → 최근 업무 페이지 조회

━━ 정리 단계 ━━
수집 완료 후 추가 툴 호출 없이 바로 한국어 마크다운으로 정리해 출력하세요.
형식: 소스별로 ## 헤더 → 항목 제목·내용·긴급도 순 나열
소스 연결 실패 시: 실패한 소스를 명시하고 나머지로 계속 진행\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) + MCP 툴(prefix 매칭) 반환."""
    local_names = set(BRIEFING_AGENT_LOCAL_TOOLS)
    return [
        t for t in all_tools
        if t.name in local_names
        or any(t.name.startswith(p) for p in BRIEFING_AGENT_MCP_PREFIXES)
    ]


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=BRIEFING_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(user_input: str) -> tuple[str, bool]:
    result = await _get_agent().ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={"recursion_limit": 15},
    )
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
