"""
Supervisor가 사용하는 SubAgent @tool 래핑.
각 subagent의 run() 함수를 도구로 노출한다.
"""
from __future__ import annotations

from langchain_core.tools import tool
from langgraph.types import interrupt

from backend.agents.tools_registry import _run


@tool
def fetch_agent(request: str) -> str:
    """Slack/Jira/Notion에서 업무 데이터를 수집합니다. 복귀 브리핑, 최근 활동 파악, 쌓인 업무 확인 시 사용."""
    from backend.agents.subagents.briefing_agent import run
    text, _ = _run(run(request))
    return text


@tool
def report_agent(request: str, context: str = "") -> str:
    """업무 데이터를 분석해 보고서를 작성합니다. fetch_agent 결과를 context 파라미터로 전달하면 더 정확한 보고서가 생성됩니다."""
    from backend.agents.subagents.report_agent import run
    full_context = f"[수집 데이터]\n{context}\n\n[요청]\n{request}" if context else request
    text, _ = _run(run(full_context))
    return text


@tool
def search_agent(query: str) -> str:
    """사내 규정, 과거 업무 항목, Slack/Jira/Notion 내용을 검색합니다."""
    from backend.agents.subagents.search_agent import run
    text, _ = _run(run(query))
    return text


@tool
def action_agent(request: str) -> str:
    """답장 초안 작성, 업무 완료 처리, Slack 발송, Jira 업데이트 등 액션을 실행합니다. 실행 전 사용자 확인이 필요합니다."""
    # HitL: write 가능 액션 → 실행 전 사용자 확인 필수
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
