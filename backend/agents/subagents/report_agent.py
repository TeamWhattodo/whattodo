from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

REPORT_AGENT_LOCAL_TOOLS: list[str] = [
    "fetch_uploaded_file",
    "parse_billing_data",
    "parse_receipt",
    "compute_daily_stats",
    "compute_kpi",
    "write_report",
]

REPORT_AGENT_SYSTEM = """\
당신은 리포트 작성 전담 에이전트입니다.
사용 가능한 tool: fetch_uploaded_file, parse_billing_data, parse_receipt,
                  compute_daily_stats, compute_kpi, write_report

제약:
- parse_billing_data / parse_receipt는 fetch_uploaded_file 완료 후 실행
- write_report는 compute 계열 tool 완료 후 실행
- 파일이 없으면 fetch_uploaded_file 생략 가능

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) 반환. MCP 없음."""
    allowed = set(REPORT_AGENT_LOCAL_TOOLS)
    return [t for t in all_tools if t.name in allowed]


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=REPORT_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(user_input: str) -> tuple[str, bool]:
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=user_input)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    has_write = any(getattr(m, "name", "") == "write_report" for m in messages)
    return output_text, has_write


def report_agent_node(state: WhatToDoState) -> WhatToDoState:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        **state,
        "results": {**state.get("results", {}), "report": {"text": text}},
        "has_write_output": state.get("has_write_output", False) or has_write,
    }
