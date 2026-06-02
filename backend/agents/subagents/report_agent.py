from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

REPORT_AGENT_LOCAL_TOOLS: list[str] = [
    "parse_billing_data",
    "parse_receipt_from_text",
    "compute_daily_stats",
    "compute_kpi",
    "write_report",
    "process_expense_report",
]

REPORT_AGENT_SYSTEM = """\
당신은 리포트 작성 전담 에이전트입니다.

## 모드 A — 수집 데이터 브리핑 (context가 'Gmail', 'Calendar', 'Slack', 'Jira', 'Notion' 관련 내용일 경우)
fetch_agent가 수집한 원본 데이터를 받아 한국어 마크다운 브리핑으로 정리합니다.
툴 호출 없이 바로 포맷팅하세요.

출력 형식:
## 📋 업무 브리핑

### 🔴 긴급
- 출처 · 내용 · 시각

### 🟡 중요
- 출처 · 내용 · 시각

### 🟢 일반
- 출처 · 내용 · 시각

긴급도 기준: 마감 초과·[긴급] 태그·High 우선순위 → 🔴 / Medium·답변 필요 → 🟡 / 나머지 → 🟢

## 모드 B — 리포트 작성 (context가 영수증 정보인 경우)
첨부 파일 내용은 이미 추출되어 context에 텍스트로 포함됩니다. 파일 경로는 제공되지 않습니다.
context의 "첨부된 문서 내용" 텍스트를 직접 tool 인자로 전달하세요.

사용 가능한 tool: parse_billing_data, parse_receipt_from_text,
                  compute_daily_stats, compute_kpi, write_report, process_expense_report

제약:
- 영수증 텍스트 → parse_receipt_from_text(text=<영수증 텍스트>) 또는 process_expense_report(receipt_text=<영수증 텍스트>)
- 정산 데이터 텍스트 → parse_billing_data에 해당 텍스트 전달
- write_report는 compute 계열 tool 완료 후 실행
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


import json

async def _run_async(context: str) -> tuple[str, bool, list[dict]]:
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=context)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""

    reports = []
    has_write = False
    for m in messages:
        if getattr(m, "name", "") in ["write_report", "process_expense_report"]:
            has_write = True
            try:
                reports.append(json.loads(m.content))
            except Exception:
                pass

    return output_text, has_write, reports


async def run(context: str) -> tuple[str, list[dict]]:
    """Supervisor report_agent tool 연결용 shim."""
    text, _, reports = await _run_async(context)
    return text, reports


def report_agent_node(state: WhatToDoState) -> dict:
    text, has_write, reports = _run(_run_async(state["user_input"]))
    return {
        "results": {"report": {"text": text, "reports": reports}},
        "has_write_output": has_write,
    }
