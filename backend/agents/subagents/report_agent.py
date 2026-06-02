from __future__ import annotations

import json

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools

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
정산·KPI·영수증 등 파일 기반 데이터를 받아 리포트를 작성합니다.

첨부 파일 내용은 이미 추출되어 context에 텍스트로 포함됩니다. 파일 경로는 제공되지 않습니다.
context의 "첨부된 문서 내용" 텍스트를 직접 tool 인자로 전달하세요.

사용 가능한 tool: parse_billing_data, parse_receipt_from_text,
                  compute_daily_stats, compute_kpi, write_report, process_expense_report

제약:
- 영수증 텍스트 → parse_receipt_from_text(text=<영수증 텍스트>) 또는 process_expense_report(receipt_text=<영수증 텍스트>)
- 정산 데이터 텍스트 → parse_billing_data에 해당 텍스트 전달
- write_report는 compute 계열 tool 완료 후 실행

경비정산서 작성 규칙 (중요):
- 영수증이 여러 개여도 process_expense_report는 반드시 한 번만 호출한다.
- context의 모든 영수증 텍스트를 하나의 receipt_text 인자에 합쳐서 전달한다.
  (영수증 사이는 줄바꿈으로 구분. 여러 영수증이 한 정산서에 모두 포함되어야 한다.)
- 영수증마다 process_expense_report를 따로 호출하지 마라. 파일이 여러 개로 쪼개진다.

경비정산서 응답 형식 (중요):
- process_expense_report 결과의 items 배열을 절대 요약·생략하지 마라.
- 영수증이 1개든 여러 개든 항상 모든 항목을 마크다운 표로 나열한다.
  열: 날짜 | 상호명 | 분류 | 금액
- 표 아래에 총액(total_amount)을 별도로 표시한다.
- 항목이 많아도 총액만 표시하고 끝내지 마라. 반드시 항목 표 전체를 포함한다.
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
            model=get_llm("smart"),
            tools=_build_tools(load_all_tools()),
            system_prompt=REPORT_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(context: str) -> tuple[str, list[dict]]:
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=context)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""

    reports = []
    expense = None  # 경비정산서는 여러 번 호출돼도 마지막 1개만 표시
    for m in messages:
        name = getattr(m, "name", "")
        if name == "process_expense_report":
            try:
                expense = json.loads(m.content)
            except Exception:
                pass
        elif name == "write_report":
            try:
                reports.append(json.loads(m.content))
            except Exception:
                pass

    if expense is not None:
        reports.append(expense)

    return output_text, reports


async def run(context: str) -> tuple[str, list[dict]]:
    """Supervisor report_agent tool 연결용 shim."""
    return await _run_async(context)
