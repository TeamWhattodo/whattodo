from __future__ import annotations

import json
from datetime import datetime

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, ToolMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

_GMAIL_TOOLS = {"fetch_gmail"}
_CALENDAR_TOOLS = {"fetch_calendar"}
_SLACK_TOOLS = {"slack_list_channels", "fetch_slack_as_items"}
_JIRA_TOOLS = {"jira_search_issues"}
_NOTION_TOOLS = {"notion_search", "notion_get_page_content"}

FETCH_AGENT_SYSTEM = """\
당신은 업무 데이터 수집 전담 에이전트입니다.
제공된 tool을 모두 호출해 데이터를 수집하고, 수집한 내용을 **있는 그대로** 나열하세요.
요약·분석·우선순위 판단은 하지 마세요. 후속 에이전트가 처리합니다.
툴이 반환한 실제 데이터만 출력하세요. 예시·가상 데이터·추측을 절대 사용하지 마세요.

━━ 소스별 수집 방법 ━━

[Gmail] — fetch_gmail 사용 시
사용자 요청에 따라 query 파라미터를 결정하여 호출:
- 읽지 않은 메일만: fetch_gmail(max_results=N, query="is:unread")
- 읽은 메일만:      fetch_gmail(max_results=N, query="is:read")
- 전체 메일:        fetch_gmail(max_results=N, query="")
- 기본(미지정):     fetch_gmail(max_results=N, query="is:unread")
결과 항목을 그대로 나열

[Calendar] — fetch_calendar 사용 시
fetch_calendar(days=14) 호출 → 결과 항목을 그대로 나열

[Slack] — slack_list_channels, fetch_slack_as_items 사용 시
① slack_list_channels(limit=100) 호출
② is_member=true 인 채널만 추린다
③ 추린 채널 각각에 fetch_slack_as_items(channel_id=<id>) 호출
   ※ channel_id 는 반드시 C로 시작하는 id 값 사용

[Jira] — jira_search_issues 사용 시
jira_search_issues(jql="statusCategory not in (Done) ORDER BY updated DESC", max_results=20)

[Notion] — notion_search, notion_get_page_content 사용 시
① notion_search(query="") → 최근 수정 상위 5개 선택
② 각 페이지에 notion_get_page_content(page_id=<id>) 호출

━━ 출력 형식 ━━

소스별로 구분해 수집한 항목을 나열. 마크다운 헤더 없이 평문으로.

[Gmail]
- 발신자: OOO | 제목: OOO | 날짜: OOO

[Calendar]
- 일정명: OOO | 시간: OOO | 주최자: OOO

[Slack]
- 채널: OOO | 발신자: OOO | 내용: OOO

[Jira]
- 키: OOO | 제목: OOO | 상태: OOO | 우선순위: OOO

[Notion]
- 페이지: OOO | 내용: OOO

소스 연결 실패 시 해당 소스를 명시하고 나머지로 계속 진행\
"""


def _jira_to_workitem(issue: dict) -> dict | None:
    key = issue.get("key") or issue.get("id", "")
    if not key:
        return None
    fields = issue.get("fields", issue)
    summary = fields.get("summary", key)
    status_data = fields.get("status", {})
    assignee_data = fields.get("assignee") or {}
    assignee = assignee_data.get("displayName", "") if isinstance(assignee_data, dict) else ""
    return {
        "id": f"jira_{key}",
        "source": "jira",
        "source_id": key,
        "raw_content": json.dumps(issue, ensure_ascii=False, default=str),
        "summary": summary,
        "urgency_level": 0,
        "urgency_breakdown": {},
        "action_type": "review",
        "from_person": assignee or None,
        "due_at": fields.get("duedate"),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }


def _notion_to_workitem(page: dict) -> dict | None:
    page_id = page.get("id", "")
    if not page_id:
        return None
    title = ""
    for prop in page.get("properties", {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            items = prop.get("title", [])
            if items:
                title = items[0].get("plain_text", "")
                break
    if not title:
        title = page.get("url", page_id)
    return {
        "id": f"notion_{page_id}",
        "source": "notion",
        "source_id": page_id,
        "raw_content": json.dumps(page, ensure_ascii=False, default=str),
        "summary": title,
        "urgency_level": 0,
        "urgency_breakdown": {},
        "action_type": "review",
        "from_person": None,
        "due_at": None,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }


def _save_mcp_results(messages: list) -> None:
    from backend.tools.storage import save_items
    items: list[dict] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        tool_name = getattr(msg, "name", "") or ""
        content = msg.content if isinstance(msg.content, str) else ""
        if not content:
            continue
        try:
            data = json.loads(content)
        except Exception:
            continue
        if "jira" in tool_name.lower():
            issues = data if isinstance(data, list) else data.get("issues", [])
            for issue in (issues or []):
                item = _jira_to_workitem(issue)
                if item:
                    items.append(item)
        elif "notion" in tool_name.lower() and "search" in tool_name.lower():
            pages = data.get("results", []) if isinstance(data, dict) else []
            for page in (pages or []):
                item = _notion_to_workitem(page)
                if item:
                    items.append(item)
    if items:
        save_items(items)


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
        system_prompt=FETCH_AGENT_SYSTEM,
    )


async def _run_async(user_input: str) -> str:
    sources = _detect_sources(user_input)
    result = await _get_agent(sources).ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={"recursion_limit": 50},
    )
    messages = result["messages"]
    _save_mcp_results(messages)
    return messages[-1].content if messages else ""


async def run(user_input: str) -> tuple[str, dict]:
    """Supervisor fetch_agent tool 연결용 shim."""
    text = await _run_async(user_input)
    return text, {}


def fetch_agent_node(state: WhatToDoState) -> dict:
    text = _run(_run_async(state["user_input"]))
    return {"results": {"briefing": {"text": text}}}
