from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

ACTION_AGENT_TOOLS: list[str] = [
    "search_past_items",
    "get_item_thread",
    "write_draft",
    "update_item_status",
    "create_calendar_block",
    "slack_get_thread_replies",
    "slack_post_message",
    "jira_add_comment",
    "notion_create_page",
]

ACTION_AGENT_SYSTEM = """\
당신은 액션 처리 전담 에이전트입니다.
사용 가능한 tool: search_past_items, get_item_thread,
                  write_draft, update_item_status, create_calendar_block,
                  slack_get_thread_replies, slack_post_message,
                  jira_add_comment, notion_create_page

제약:
- write_draft는 get_item_thread 또는 slack_get_thread_replies로 맥락 확보 후 실행 권장
- 발송·수정 액션(slack_post_message, jira_add_comment, notion_create_page)은 사용자 확인 후 실행
- create_calendar_block은 반드시 사용자 확인 후 실행

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.\
"""


def _build_tools(all_tools: list) -> list:
    allowed = set(ACTION_AGENT_TOOLS)
    return [t for t in all_tools if t.name in allowed]


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=ACTION_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(user_input: str) -> tuple[str, bool]:
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=user_input)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    has_write = any(getattr(m, "name", "") == "write_draft" for m in messages)
    return output_text, has_write


def action_agent_node(state: WhatToDoState) -> dict:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        "results": {"action": {"text": text}},
        "has_write_output": has_write,
    }
