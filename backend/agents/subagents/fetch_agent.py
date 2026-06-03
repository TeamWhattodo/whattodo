from __future__ import annotations

import json

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

FETCH_AGENT_SYSTEM = """\
당신은 로컬 DB에서 업무 데이터를 조회하는 전담 에이전트입니다.
반드시 read_work_items 툴만 사용하세요. 외부 API는 절대 호출하지 마세요.

━━ 조회 방법 ━━

사용자가 요청한 소스와 개수에 맞게 read_work_items를 호출하세요.

예시:
- "메일 5개" → read_work_items(source="gmail", limit=5)
- "슬랙 메시지" → read_work_items(source="slack", limit=20)
- "전체 업무 현황" → read_work_items(source="", limit=50)
- "Jira 이슈" → read_work_items(source="jira", limit=20)
- "캘린더 일정" → read_work_items(source="calendar", limit=20)
- "긴급한 항목" → read_work_items(source="", status="pending", limit=20)
- 특정 키워드 검색 → read_work_items(query="키워드", limit=20)

━━ 출력 형식 ━━

툴이 반환한 JSON 데이터를 그대로 출력하세요.
요약·분석·우선순위 판단은 하지 마세요. 후속 에이전트가 처리합니다.\
"""


def _build_tools(all_tools: list) -> list:
    return [t for t in all_tools if t.name == "read_work_items"]


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=FETCH_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(user_input: str) -> str:
    result = await _get_agent().ainvoke(
        {"messages": [HumanMessage(content=user_input)]},
        config={"recursion_limit": 20},
    )
    messages = result["messages"]
    # read_work_items 툴 결과(JSON)를 직접 반환
    for msg in reversed(messages):
        if hasattr(msg, "name") and msg.name == "read_work_items":
            return msg.content if isinstance(msg.content, str) else ""
    # 툴 호출이 없었으면 마지막 AIMessage 반환
    return messages[-1].content if messages else ""


async def run(user_input: str) -> tuple[str, dict]:
    """Supervisor fetch_agent tool 연결용 shim."""
    text = await _run_async(user_input)
    return text, {}


def fetch_agent_node(state: WhatToDoState) -> dict:
    text = _run(_run_async(state["user_input"]))
    return {"results": {"briefing": {"text": text}}}
