from __future__ import annotations

import json

from langchain_core.tools import tool
from langgraph.types import interrupt

from backend.agents.tools_registry import _run


@tool
def fetch_agent(request: str) -> str:
    """Gmail·Calendar·Slack·Jira·Notion에서 업무 데이터를 수집합니다.
    브리핑·복귀 정리·소스별 현황 파악 시 사용. 수집 결과를 report_agent에 context로 전달하세요."""
    from backend.agents.subagents.fetch_agent import run
    text, _ = _run(run(request))
    return text


@tool
def report_agent(request: str, context: str = "") -> str:
    """업무 데이터를 분석해 브리핑 또는 보고서를 작성합니다.
    fetch_agent 결과를 context에 전달하면 마크다운 브리핑을 생성합니다.
    파일(정산·KPI·영수증) 기반 리포트도 처리합니다."""
    from backend.agents.subagents.report_agent import run
    full_input = f"[수집 데이터]\n{context}\n\n[요청]\n{request}" if context else request
    text, reports = _run(run(full_input))
    if reports:
        return json.dumps({"text": text, "reports": reports}, ensure_ascii=False, default=str)
    return text


@tool
def search_agent(query: str) -> str:
    """사내 규정·과거 업무 항목·캘린더 일정·Slack·Jira·Notion을 검색합니다.
    특정 항목 조회, 규정 확인, 스레드 내용 확인 시 사용."""
    from backend.agents.subagents.search_agent import run
    text, _ = _run(run(query))
    return text


@tool
def action_agent(request: str) -> str:
    """Gmail 발송·삭제, Slack 메시지 발송·삭제, Jira 이슈 관리,
    Notion 페이지 관리, 캘린더 일정 생성·삭제, 답장 초안 작성을 실행합니다.
    실행 전 사용자 확인이 필요합니다."""
    answer = interrupt({
        "type": "action_confirmation",
        "message": f"다음 액션을 실행하시겠습니까?\n\n**요청**: {request}",
        "request": request,
    })
    if str(answer).strip().lower() in ("n", "no", "아니오", "취소", ""):
        return "사용자가 취소했습니다."
    from backend.agents.subagents.action_agent import run
    text, _ = _run(run(request))
    return text


SUPERVISOR_TOOLS = [fetch_agent, report_agent, search_agent, action_agent]
