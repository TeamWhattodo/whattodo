"""
storage 툴 — 담당 #5.
TinyDB CRUD. db/store.py의 공개 인터페이스.
"""
from backend.models import BriefingResult, DailySummary, KPIReport, WorkCard


def save_work_items(user_id: str, cards: list[WorkCard]) -> None:
    ...


def get_pending_cards(user_id: str) -> list[WorkCard]:
    ...


def update_item_status(item_id: str, status: str) -> None:
    ...


def save_briefing(user_id: str, result: BriefingResult) -> None:
    ...


def get_latest_briefing(user_id: str) -> BriefingResult | None:
    ...


def save_daily_summary(user_id: str, summary: DailySummary) -> None:
    ...


def get_daily_summary(user_id: str, date: str) -> DailySummary | None:
    ...


def save_kpi_report(user_id: str, report: KPIReport) -> None:
    ...


def get_latest_kpi_report(user_id: str) -> KPIReport | None:
    ...


def finalize_briefing(cards: list[WorkCard], absence_days: int, user_id: str) -> BriefingResult:
    """브리핑 헤더 생성 + TinyDB 저장 후 BriefingResult 반환. 담당 #5."""
    ...
