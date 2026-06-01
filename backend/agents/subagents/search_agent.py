from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

_GENERAL_TOOLS = {"search_past_items", "search_company_docs", "get_item_thread"}
_GMAIL_TOOLS = {"fetch_gmail"}
_CALENDAR_TOOLS = {"fetch_calendar", "search_calendar_events"}
_SLACK_TOOLS = {"slack_search_messages"}
_JIRA_TOOLS = {"jira_search_issues"}
_NOTION_TOOLS = {"notion_search", "notion_get_page_content"}

SEARCH_AGENT_SYSTEM = """\
당신은 조회 전담 에이전트입니다.
툴이 반환한 실제 데이터만 출력하세요. 데이터를 만들어내거나 예시를 사용하지 마세요.

## 툴 선택 기준
- 특정 item_id(32자 hex)의 내용·스레드 요청 → get_item_thread(item_id, source) 사용
- 특정 메일·메시지 내용 조회 → search_past_items로 항목 찾은 뒤 get_item_thread로 상세 내용 반환
- 사내 규정·정책·한도 질문 → search_company_docs 우선 사용
- 과거 업무 항목 검색 → search_past_items 사용
- 메일·이메일 관련 질문 → fetch_gmail(max_results=20) 호출
- 캘린더·일정 관련 질문 → search_calendar_events 또는 fetch_calendar 사용
- Slack 메시지 검색 → slack_search_messages
- Jira 이슈 검색 → jira_search_issues(jql=...)
- Notion 내용 조회 → notion_search 후 notion_get_page_content 순서로 실행

## 검색 방법
- search_past_items의 query에는 사용자 문장 전체가 아닌 **핵심 키워드만** 입력
  예) "신현섭 테스트 메시지 내용 보고싶어" → query="테스트 메시지" 또는 query="신현섭"
- 첫 검색에서 안 나오면 query를 더 짧게 줄여서 재시도
- source 파라미터로 범위 좁히기 가능 (gmail·slack·jira)

## 출력 규칙
- get_item_thread 결과가 있으면 발신자·제목·본문을 정리해서 출력
- 결과가 없으면 "해당 항목을 찾을 수 없습니다"로 출력
- 절대 툴 호출 없이 메일·일정 내용을 지어내지 마세요\
"""


def _detect_sources(text: str) -> list[str]:
    t = text.lower()
    sources = list(_GENERAL_TOOLS)  # 항상 포함
    if any(w in t for w in ["gmail", "메일", "이메일", "mail"]):
        sources.append("gmail")
    if any(w in t for w in ["calendar", "캘린더", "일정", "스케줄"]):
        sources.append("calendar")
    if any(w in t for w in ["slack", "슬랙", "슬렉"]):
        sources.append("slack")
    if any(w in t for w in ["jira", "지라", "이슈", "티켓", "스프린트"]):
        sources.append("jira")
    if any(w in t for w in ["notion", "노션", "문서", "페이지"]):
        sources.append("notion")
    return sources


def _build_tools(all_tools: list, sources: list) -> list:
    allowed = set(_GENERAL_TOOLS)
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
        system_prompt=SEARCH_AGENT_SYSTEM,
    )


async def _run_async(user_input: str) -> tuple[str, bool]:
    sources = _detect_sources(user_input)
    result = await _get_agent(sources).ainvoke({"messages": [HumanMessage(content=user_input)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    return output_text, False


async def run(query: str) -> tuple[str, bool]:
    """Supervisor search_agent tool 연결용 shim."""
    return await _run_async(query)


def search_agent_node(state: WhatToDoState) -> dict:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        "results": {"search": {"text": text}},
        "has_write_output": has_write,
    }
