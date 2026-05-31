from __future__ import annotations

from datetime import date
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

ACTION_AGENT_LOCAL_TOOLS: list[str] = [
    "search_past_items",
    "get_item_thread",
    "write_draft",
    "update_item_status",
    "create_calendar_block",
]

ACTION_AGENT_MCP_TOOLS: list[str] = [
    "slack_get_thread_replies",
    "slack_post_message",
    "jira_update_issue",
    "API-patch-page",
]

def _build_system_prompt() -> str:
    today = date.today().strftime("%Y-%m-%d")
    return f"""\
당신은 액션 처리 전담 에이전트입니다.
오늘 날짜: {today}

## 원칙
- 사용자 요청에서 필요한 모든 정보(날짜·시간·제목 등)를 직접 파악해 툴을 즉시 호출하세요.
- 날짜·시간은 자연어("내일 오후 2시")를 오늘 날짜 기준으로 ISO 8601 형식으로 **에이전트가 직접 변환**합니다. 사용자에게 형식을 요구하지 마세요.
- 추가 정보가 충분하면 바로 툴을 호출하고, 결과를 사용자에게 보여주세요.

## 툴 사용 순서
- write_draft는 get_item_thread 또는 slack_get_thread_replies로 맥락 확보 후 실행
- 발송·수정 액션(slack_post_message, jira_update_issue, API-patch-page)은 툴 호출 전 실행 내용을 사용자에게 보여주고 승인 요청
- create_calendar_block은 툴 호출 전 생성될 일정 정보(제목·시작·종료)를 사용자에게 보여주고 승인 요청

## 사용 가능한 툴
search_past_items, get_item_thread, write_draft, update_item_status, create_calendar_block,
slack_get_thread_replies, slack_post_message, jira_update_issue, API-patch-page\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) + MCP 툴(이름 매칭) 반환."""
    allowed = set(ACTION_AGENT_LOCAL_TOOLS) | set(ACTION_AGENT_MCP_TOOLS)
    return [t for t in all_tools if t.name in allowed]


_agent = None
_agent_date: str = ""


def _get_agent():
    global _agent, _agent_date
    today = date.today().strftime("%Y-%m-%d")
    if _agent is None or _agent_date != today:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=_build_system_prompt(),
        )
        _agent_date = today
    return _agent


async def _run_async(messages: list) -> tuple[str, bool]:
    result = await _get_agent().ainvoke({"messages": messages})
    out_messages = result["messages"]
    output_text = out_messages[-1].content if out_messages else ""
    has_write = any(getattr(m, "name", "") == "write_draft" for m in out_messages)
    return output_text, has_write


def action_agent_node(state: WhatToDoState) -> dict:
    messages = state.get("messages") or [HumanMessage(content=state["user_input"])]
    text, has_write = _run(_run_async(messages))
    return {
        "results": {"action": {"text": text}},
        "has_write_output": has_write,
    }
