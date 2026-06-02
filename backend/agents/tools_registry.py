"""
전체 @tool 래퍼를 담당한다.
SubAgent와 orchestrator 양쪽에서 import해 사용한다.
"""
import asyncio
import json
import threading

from langchain_core.tools import tool
from backend.tools.scoring import score_urgency as _score_urgency
from backend.tools.classify import classify_items as _classify, filter_items as _filter
from backend.tools.write_report import write_report as _write_report
from backend.tools.write_draft import write_draft as _write_draft
from backend.tools.update_status import update_item_status as _update_status, create_calendar_block as _create_calendar_block, delete_calendar_block as _delete_calendar_block
from backend.tools.search_items import search_past_items as _search, get_item_thread as _get_item_thread
from backend.tools.policy_search import search_company_docs as _search_docs
from backend.tools.parse_billing import parse_billing_data as _parse_billing
from backend.tools.compute_stats import compute_daily_stats as _compute_daily, compute_kpi as _compute_kpi
from backend.tools.receipt import parse_receipt_from_text as _parse_receipt_from_text
from backend.tools.gmail_fetch import fetch_gmail as _fetch_gmail, send_gmail as _send_gmail, trash_gmail as _trash_gmail
from backend.tools.calendar_fetch import fetch_calendar as _fetch_calendar, search_calendar_events as _search_calendar
from backend.tools.spellcheck import check_spelling as _check_spelling
from backend.tools.slack_fetch import SLACK_TOOLS, fetch_slack_as_items
from backend.tools.jira_fetch import JIRA_TOOLS
from backend.tools.notion_fetch import NOTION_TOOLS, list_notion_pages

# ── @tool 래퍼 ────────────────────────────────────────────────────────────────

@tool
def score_urgency(items: list) -> str:
    """WorkItem 목록에 긴급도(1~5)를 계산합니다. LLM 미사용."""
    return json.dumps(_score_urgency(items), ensure_ascii=False, default=str)


@tool
def classify_items(items: list) -> str:
    """항목에 액션 타입(reply/approve/review/fyi/none)과 요약을 부여합니다. LLM Fast 티어 사용."""
    return json.dumps(_classify(items), ensure_ascii=False, default=str)


@tool
def filter_items(items: list, min_urgency: int = 3) -> str:
    """urgency_level >= min_urgency 인 항목만 필터링합니다."""
    return json.dumps(_filter(items, min_urgency), ensure_ascii=False, default=str)


@tool
def write_report(report_type: str, data: str) -> str:
    """업무 보고서를 작성합니다. report_type: briefing | daily_summary | kpi_weekly | billing. data: JSON 문자열."""
    try:
        parsed = json.loads(data)
    except Exception:
        parsed = data
    return json.dumps(_write_report(report_type, parsed), ensure_ascii=False, default=str)


@tool
def write_draft(item_id: str, tone: str = "formal") -> str:
    """item_id로 항목을 조회해 답장 초안을 생성합니다. tone: formal | casual."""
    return json.dumps(_write_draft(item_id, tone), ensure_ascii=False, default=str)


@tool
def update_item_status(item_id: str, status: str) -> str:
    """항목 상태를 변경합니다. status: done | snoozed | pending."""
    return json.dumps(_update_status(item_id, status), ensure_ascii=False, default=str)


@tool
def search_past_items(query: str = "", status: str = "", source: str = "") -> str:
    """저장된 WorkItem을 검색합니다. query: 키워드, status: done|pending|snoozed, source: gmail|slack|jira."""
    return json.dumps(
        _search(query=query, status=status or None, source=source or None),
        ensure_ascii=False, default=str,
    )


@tool
def get_item_thread(item_id: str, source: str) -> str:
    """특정 항목의 스레드 전체를 조회합니다. write_draft 실행 전 맥락 확보용. source: gmail|slack|jira."""
    return json.dumps(_get_item_thread(item_id, source), ensure_ascii=False, default=str)


@tool
def create_calendar_block(title: str, start: str, end: str) -> str:
    """캘린더 일정을 생성합니다. title: 일정 제목. start/end: ISO 8601 (예: 2026-06-01T14:00:00). 에이전트가 자연어 시간을 직접 변환해 호출."""
    return json.dumps(_create_calendar_block(title, start, end), ensure_ascii=False, default=str)


@tool
def delete_calendar_block(event_id: str) -> str:
    """캘린더 일정을 삭제합니다. event_id: Google Calendar 이벤트 ID. 반드시 사용자 확인 후 실행."""
    return json.dumps(_delete_calendar_block(event_id), ensure_ascii=False, default=str)


@tool
def search_calendar_events(query: str = "", days: int = 30) -> str:
    """Google Calendar에서 일정을 검색합니다. query: 제목 키워드. days: 오늘부터 몇 일 이내 검색(기본 30일). event_id 포함 반환."""
    return json.dumps(_search_calendar(query=query, days=days), ensure_ascii=False, default=str)


@tool
def search_company_docs(query: str, top_k: int = 3) -> str:
    """사내 규정·문서에서 query와 관련된 내용을 검색합니다. 규정 조회, 정산 검증, 미팅 준비 시 사용."""
    return _search_docs(query, top_k)


@tool
def parse_billing_data(billing_text: str, month: str) -> str:
    """추출된 정산 텍스트를 파싱합니다. month: YYYY-MM 형식."""
    return json.dumps(_parse_billing(billing_text, month), ensure_ascii=False, default=str)


@tool
def parse_receipt_from_text(text: str) -> str:
    """영수증 텍스트를 구조화해 항목(날짜·가맹점·금액·카테고리)을 추출합니다."""
    return json.dumps(_parse_receipt_from_text(text), ensure_ascii=False, default=str)


@tool
def compute_daily_stats(date: str) -> str:
    """특정 날짜의 완료·이월·처리 통계를 집계합니다. date: YYYY-MM-DD 형식."""
    return json.dumps(_compute_daily(date), ensure_ascii=False, default=str)


@tool
def compute_kpi(period: str = "weekly") -> str:
    """완료율·응답시간·채널별 부하 등 생산성 KPI를 집계합니다. period: weekly | monthly."""
    return json.dumps(_compute_kpi(period), ensure_ascii=False, default=str)


@tool
def send_gmail(to: str, subject: str, body: str, thread_id: str = "") -> str:
    """Gmail로 이메일을 발송합니다. to: 수신자 이메일. subject: 제목. body: 본문. thread_id: 답장 시 원본 threadId. 반드시 사용자 확인 후 실행."""
    return json.dumps(_send_gmail(to=to, subject=subject, body=body, thread_id=thread_id), ensure_ascii=False, default=str)


@tool
def trash_gmail(message_id: str) -> str:
    """Gmail 메시지를 휴지통으로 이동합니다. message_id: Gmail 메시지 ID. 반드시 사용자 확인 후 실행."""
    return json.dumps(_trash_gmail(message_id=message_id), ensure_ascii=False, default=str)


@tool
def fetch_gmail(max_results: int = 20) -> str:
    """Gmail 미읽음 메일을 가져와 WorkItem 목록으로 반환합니다. 가져온 항목은 자동으로 저장됩니다. Google 인증이 필요합니다."""
    from backend.tools.storage import save_items
    items = _fetch_gmail(max_results)
    items_dict = [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]
    save_items(items_dict)
    return json.dumps(items_dict, ensure_ascii=False, default=str)


@tool
def fetch_calendar(days: int = 7) -> str:
    """Google Calendar 일정을 가져와 WorkItem 목록으로 반환합니다. days: 조회할 일수(기본 7일)."""
    return json.dumps(_fetch_calendar(days), ensure_ascii=False, default=str)


@tool
def process_expense_report(receipt_text: str) -> str:
    """영수증 텍스트를 분석해 경비정산서(엑셀·PDF)를 작성합니다. receipt_text: 추출된 영수증 텍스트."""
    from backend.tools.receipt import parse_receipt_from_text
    from backend.tools.expense import build_expense_report
    items = parse_receipt_from_text(receipt_text)
    report = build_expense_report(items)
    return json.dumps({
        "report_type":  report["report_type"],
        "total_amount": report["total_amount"],
        "items":        report["items"],
        "xlsx_path":    report["xlsx_path"],
    }, ensure_ascii=False, default=str)


@tool
def spell_check(text: str) -> str:
    """주어진 한국어 텍스트의 맞춤법, 띄어쓰기, 어색한 문맥을 교정합니다. text: 교정할 원본 텍스트."""
    return json.dumps(_check_spelling(text), ensure_ascii=False, default=str)


LOCAL_TOOLS = [
    score_urgency,
    classify_items,
    filter_items,
    write_report,
    write_draft,
    update_item_status,
    search_past_items,
    get_item_thread,
    send_gmail,
    trash_gmail,
    create_calendar_block,
    delete_calendar_block,
    search_calendar_events,
    search_company_docs,
    parse_billing_data,
    parse_receipt_from_text,
    compute_daily_stats,
    compute_kpi,
    fetch_gmail,
    fetch_calendar,
    process_expense_report,
    spell_check,
    list_notion_pages,
    *SLACK_TOOLS,
    *JIRA_TOOLS,
    *NOTION_TOOLS,
]


# ── 비동기 실행 헬퍼 ──────────────────────────────────────────────────────────

_bg_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
threading.Thread(target=_bg_loop.run_forever, daemon=True).start()


def _run(coro):
    return asyncio.run_coroutine_threadsafe(coro, _bg_loop).result()


ALL_TOOLS: list = LOCAL_TOOLS


def load_all_tools() -> list:
    """로컬 @tool 전체 목록을 반환한다."""
    return ALL_TOOLS
