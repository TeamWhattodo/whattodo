from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

BRIEFING_AGENT_LOCAL_TOOLS: list[str] = []

BRIEFING_AGENT_MCP_TOOLS: list[str] = [
    "slack_list_channels",
    "slack_get_channel_history",
    "jira_search",
    "API-post-search",
    "API-get-block-children",
]

BRIEFING_AGENT_SYSTEM = """\
당신은 브리핑 전담 에이전트입니다.

사용 가능한 tool: slack_list_channels, slack_get_channel_history, jira_search, API-post-search

━━ 수집 소스 결정 ━━

먼저 사용자 요청에서 수집할 소스를 판단한다.
- "Slack" 언급 또는 메시지·채널·DM 관련 요청 → Slack 수집
- "Jira" 언급 또는 이슈·티켓·스프린트 관련 요청 → Jira 수집
- "Notion" 언급 또는 문서·페이지·노션 관련 요청 → Notion 수집
- 특정 소스를 언급하지 않은 전체 브리핑 요청 → 세 소스 모두 수집

━━ 소스별 수집 방법 ━━

[Slack]
① slack_list_channels(limit=100) 호출
② 응답에서 is_member=true 인 채널만 추린다
③ 추린 채널 각각에 slack_get_channel_history(channel_id=<id>, limit=50) 호출
   ※ channel_id 는 반드시 C로 시작하는 id 값 사용 (채널 이름 절대 금지)
   ※ ③은 생략 불가 — 채널 description은 메시지가 아님

[Jira]
jira_search(jql="statusCategory not in (Done) ORDER BY updated DESC", limit=20)

[Notion]
① API-post-search(query="") → 페이지 목록 수집
② 수집된 페이지 중 최근 수정일 기준 상위 5개를 선택
③ 선택된 페이지 각각에 API-get-block-children(block_id=<page_id>) 호출해 내용 확인
   ※ ③은 생략 불가 — 페이지 제목만으로는 내용을 알 수 없음

━━ 정리 출력 ━━

수집 완료 후 추가 툴 호출 없이 수집한 소스에 대해서만 한국어 마크다운으로 출력:

## Slack (수집한 경우만)
- 채널별 실제 메시지 나열 (발신자 · 내용 · 시각)
- 업무 관련 메시지만, 채널 description · 시스템 메시지 제외
- 메시지 없는 채널은 제외

## Jira (수집한 경우만)
- 이슈 키 · 제목 · 상태 · 긴급도

## Notion (수집한 경우만)
- 페이지 제목 · 핵심 내용 요약 (내용이 없으면 제목만)

소스 연결 실패 시 해당 소스를 명시하고 나머지로 계속 진행\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) + MCP 툴(이름 매칭) 반환."""
    allowed = set(BRIEFING_AGENT_LOCAL_TOOLS) | set(BRIEFING_AGENT_MCP_TOOLS)
    return [t for t in all_tools if t.name in allowed]


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
        config={"recursion_limit": 30},
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
