from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

_GMAIL_TOOLS = {"fetch_gmail"}
_CALENDAR_TOOLS = {"fetch_calendar"}
_SLACK_TOOLS = {"slack_list_channels", "slack_get_channel_history"}
_JIRA_TOOLS = {"jira_search_issues"}
_NOTION_TOOLS = {"notion_search", "notion_get_page_content"}

BRIEFING_AGENT_SYSTEM = """\
당신은 브리핑 전담 에이전트입니다.
제공된 tool을 빠짐없이 모두 호출해 데이터를 수집하고 한국어 마크다운으로 출력하세요.
tool이 여러 개 제공된 경우 모든 소스를 수집해야 합니다. 일부만 수집하면 안 됩니다.

━━ 소스별 수집 방법 ━━

[Gmail] — fetch_gmail 사용 시
fetch_gmail(max_results=20) 호출 → 미읽음 메일 목록 수집

[Calendar] — fetch_calendar 사용 시
fetch_calendar(days=14) 호출 → 향후 14일 일정 수집

[Slack] — slack_list_channels, slack_get_channel_history 사용 시
① slack_list_channels(limit=100) 호출
② 응답에서 is_member=true 인 채널만 추린다
③ 추린 채널 각각에 slack_get_channel_history(channel_id=<id>, limit=50) 호출
   ※ channel_id 는 반드시 C로 시작하는 id 값 사용 (채널 이름 절대 금지)
   ※ ③은 생략 불가 — 채널 description은 메시지가 아님

[Jira] — jira_search_issues 사용 시
jira_search_issues(jql="statusCategory not in (Done) ORDER BY updated DESC", max_results=20)

[Notion] — notion_search, notion_get_page_content 사용 시
① notion_search(query="") → 페이지 목록 수집
② 수집된 페이지 중 최근 수정일 기준 상위 5개를 선택
③ 선택된 페이지 각각에 notion_get_page_content(page_id=<id>) 호출해 내용 확인
   ※ ③은 생략 불가 — 페이지 제목만으로는 내용을 알 수 없음

━━ 정리 출력 ━━

수집 완료 후 추가 툴 호출 없이 수집한 소스에 대해서만 출력:

## Gmail (수집한 경우만)
- 발신자 · 제목 · 날짜 나열
- 업무 관련 메일만, 광고·수신거부 메일 제외

## Calendar (수집한 경우만)
- 일정명 · 날짜/시간 · 주최자 나열
- 업무 관련 일정만

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


def _detect_sources(text: str) -> list[str]:
    t = text.lower()
    sources = []
    if any(w in t for w in ["gmail", "메일", "이메일", "mail"]):
        sources.append("gmail")
    if any(w in t for w in ["calendar", "캘린더", "schedule", "스케줄", "스케쥴", "스캐쥴", "스캐줄"]):
        sources.append("calendar")
    if any(w in t for w in ["slack", "슬랙", "슬렉", "채널", "메시지", "dm"]):
        sources.append("slack")
    if any(w in t for w in ["jira", "지라", "이슈", "티켓", "스프린트"]):
        sources.append("jira")
    if any(w in t for w in ["notion", "노션", "문서", "페이지"]):
        sources.append("notion")
    return sources or ["gmail", "calendar", "slack", "jira", "notion"]


def _build_tools(all_tools: list, sources: list) -> list:
    allowed: set[str] = set()
    if "gmail" in sources:
        allowed |= _GMAIL_TOOLS
    if "calendar" in sources:
        allowed |= _CALENDAR_TOOLS
    if "slack" in sources:
        allowed |= _SLACK_TOOLS
    if "jira" in sources:
        allowed |= _JIRA_TOOLS
    if "notion" in sources:
        allowed |= _NOTION_TOOLS
    return [t for t in all_tools if t.name in allowed]


def _get_agent(sources: list):
    return create_agent(
        model=get_llm("fast"),
        tools=_build_tools(load_all_tools(), sources),
        system_prompt=BRIEFING_AGENT_SYSTEM,
    )


async def _run_async(user_input: str) -> tuple[str, bool]:
    sources = _detect_sources(user_input)
    result = await _get_agent(sources).ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={"recursion_limit": 50},
    )
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    has_write = any(getattr(m, "name", "") == "write_report" for m in messages)
    return output_text, has_write


def briefing_agent_node(state: WhatToDoState) -> dict:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        "results": {"briefing": {"text": text}},
        "has_write_output": has_write,
    }
