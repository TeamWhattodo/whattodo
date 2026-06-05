from __future__ import annotations

import json

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools

REPORT_AGENT_LOCAL_TOOLS: list[str] = [
    "parse_receipt_from_text",
    "process_expense_report",
    "fetch_tasks",
    "write_report",
]

REPORT_AGENT_SYSTEM = """\
당신은 리포트 작성 전담 에이전트입니다.
경비정산서 작성과 주간 보고서 작성 2가지 기능을 담당합니다.

첨부 파일 내용은 이미 추출되어 context에 텍스트로 포함됩니다. 파일 경로는 제공되지 않습니다.
context의 "첨부된 문서 내용" 텍스트를 직접 tool 인자로 전달하세요.

사용 가능한 tool:
  parse_receipt_from_text, process_expense_report,
  fetch_tasks, write_report

─────────────────────────────────────────────
[1] 경비정산서  (엑셀 출력)
─────────────────────────────────────────────
트리거: "영수증", "경비정산", "정산서"

실행 순서:
  1. process_expense_report(receipt_text=<모든 영수증 텍스트 합본>) — 반드시 1회만 호출
     - 영수증 여러 개: 줄바꿈으로 구분해 하나의 receipt_text에 합친다
     - 영수증마다 따로 호출하지 마라 (파일이 쪼개짐)
  2. write_report(report_type="expense_report", data=<process_expense_report 결과 JSON>)
     - 엑셀 파일 생성은 write_report가 담당

응답 형식:
  ## 💳 경비정산서

  | 날짜 | 상호명 | 분류 | 금액 |
  |------|--------|------|------|
  | 값   | 값     | 값   | 값   |

  **총액:** N원

  - items 배열 절대 요약·생략 금지. 항목 표 전체 포함 필수.

─────────────────────────────────────────────
[2] 주간 보고서  (PDF 출력)
─────────────────────────────────────────────
트리거: "주간 보고서", "주간 보고", "이번 주 보고서"

실행 순서:
  1. 오늘 날짜 기준으로 이번 주 월요일(start)·일요일(end) 계산
  2. fetch_tasks(start=<월요일>, end=<일요일>) 호출 → 업무 목록 수집
  3. write_report(report_type="kpi_weekly", data=<fetch 결과 JSON>)
     - fetch 없이 write_report 먼저 호출 금지
     - data에 담당자·부서·직책 정보 없으면 "-" 입력
     - start/end는 YYYY-MM-DD 형식

응답 형식:
  ## 📊 주간 업무 보고서

  **기간:** YYYY-MM-DD (월) ~ YYYY-MM-DD (일)

  ### ✅ 완료 업무
  | 업무명 | 출처 | 완료날짜 |
  |--------|------|----------|
  | 값     | 값   | 값       |

  **총 완료 업무:** N건
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


async def _run_async(context: str, run_config: dict | None = None) -> tuple[str, list[dict]]:
    config = {**(run_config or {}), "recursion_limit": 20}
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=context)]}, config=config)
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


async def run(context: str, run_config: dict | None = None) -> tuple[str, list[dict]]:
    """Supervisor report_agent tool 연결용 shim."""
    return await _run_async(context, run_config=run_config)
