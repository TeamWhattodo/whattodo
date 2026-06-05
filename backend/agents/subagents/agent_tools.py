from __future__ import annotations

import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.types import interrupt

from backend.agents.tools_registry import _run


def _wrap(agent: str, status: str, content: str, **extra) -> str:
    return json.dumps(
        {"status": status, "agent": agent, "content": content, **extra},
        ensure_ascii=False,
        default=str,
    )


@tool
def fetch_agent(request: str) -> str:
    """Gmail·Calendar·Slack·Jira·Notion에서 업무 데이터를 수집합니다.
    브리핑·복귀 정리·소스별 현황 파악 시 사용."""
    from backend.agents.subagents.fetch_agent import run
    try:
        text, _ = _run(run(request))
        return _wrap("fetch", "success", text)
    except Exception as e:
        return _wrap("fetch", "error", f"수집 실패: {e}")


@tool
def briefing_agent(request: str, context: str = "") -> str:
    """fetch_agent가 수집한 업무 데이터를 마크다운 브리핑으로 정리합니다.
    복귀 브리핑·업무 현황 정리 시 fetch_agent 결과의 content를 context에 전달하세요."""
    from backend.agents.subagents.briefing_agent import run
    full_input = f"[수집 데이터]\n{context}\n\n[요청]\n{request}" if context else request
    try:
        text, reports = _run(run(full_input))
        return _wrap("report", "success", text, report_type="briefing", files=reports)
    except Exception as e:
        return _wrap("report", "error", f"브리핑 생성 실패: {e}", files=[])


def _inject_week_dates(request: str) -> str:
    from datetime import date, timedelta
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    date_info = f"\n[이번 주 날짜 범위: start={monday.strftime('%Y-%m-%d')}, end={sunday.strftime('%Y-%m-%d')}, today={today.strftime('%Y-%m-%d')}]"
    return request + date_info


@tool
def report_agent(request: str, config: RunnableConfig) -> str:
    """정산·KPI·영수증 등 파일 기반 데이터를 분석해 보고서를 작성합니다.
    추출된 첨부 문서 내용은 request에 텍스트로 포함해 전달하세요."""
    from backend.agents.subagents.report_agent import run
    try:
        run_config = {"configurable": config.get("configurable", {})}
        text, reports = _run(run(_inject_week_dates(request), run_config=run_config))
        return _wrap("report", "success", text, report_type="report", files=reports)
    except Exception as e:
        return _wrap("report", "error", f"리포트 생성 실패: {e}", files=[])


@tool
def search_agent(query: str) -> str:
    """사내 규정·정책·업무 이력을 조회합니다.
    규정 확인, 과거 항목 검색, 특정 메일·메시지 스레드 내용 확인 시 사용."""
    from backend.agents.subagents.search_agent import run
    try:
        text, _ = _run(run(query))
        status = "not_found" if "찾을 수 없습니다" in text else "success"
        return _wrap("search", status, text)
    except Exception as e:
        return _wrap("search", "error", f"검색 실패: {e}")


_DESTRUCTIVE_KEYWORDS = [
    "발송", "보내", "전송", "삭제", "제거", "완료", "처리",
    "생성", "추가", "만들어", "업데이트", "변경", "수정", "잡아",
    "send", "delete", "create", "update",
]

_ACTION_TYPE_KEYWORDS = [
    ("send_gmail",      ["메일 보내", "답장 발송", "gmail 발송"]),
    ("trash_gmail",     ["메일 삭제", "gmail 삭제"]),
    ("slack_post",      ["슬랙 보내", "slack 발송"]),
    ("slack_delete",    ["슬랙 삭제", "slack 삭제"]),
    ("create_calendar", ["일정 생성", "캘린더 추가", "캘린더 잡아"]),
    ("delete_calendar", ["일정 삭제", "캘린더 삭제"]),
    ("jira",            ["jira", "지라", "이슈"]),
    ("notion",          ["notion", "노션"]),
    ("write_draft",     ["초안", "draft"]),
]


def _detect_action_type(request: str) -> str:
    r = request.lower()
    for action_type, keywords in _ACTION_TYPE_KEYWORDS:
        if any(k in r for k in keywords):
            return action_type
    return "unknown"


@tool
def action_agent(request: str) -> str:
    """Gmail 발송·삭제, Slack 메시지 발송·삭제, Jira 이슈 관리,
    Notion 페이지 관리, 캘린더 일정 생성·삭제, 답장 초안 작성을 실행합니다.
    발송·삭제·생성 등 외부 변경이 발생하는 경우 실행 전 사용자 확인을 요청합니다."""
    needs_confirm = any(k in request for k in _DESTRUCTIVE_KEYWORDS)
    if needs_confirm:
        answer = interrupt({
            "type": "action_confirmation",
            "message": f"다음 액션을 실행하시겠습니까?\n\n**요청**: {request}",
            "request": request,
        })
        if str(answer).strip().lower() in ("n", "no", "아니오", "취소", ""):
            return _wrap("action", "cancelled", "사용자가 취소했습니다.",
                         action_type=_detect_action_type(request))
    from backend.agents.subagents.action_agent import run
    try:
        text, has_draft = _run(run(request))
        extra = {"action_type": _detect_action_type(request)}
        if has_draft:
            extra["draft"] = text
        return _wrap("action", "success", text, **extra)
    except Exception as e:
        return _wrap("action", "error", f"액션 실패: {e}",
                     action_type=_detect_action_type(request))


SUPERVISOR_TOOLS = [fetch_agent, briefing_agent, report_agent, search_agent, action_agent]
