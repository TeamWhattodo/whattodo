"""
storage 툴 — 담당 #5.
TinyDB CRUD. db/store.py의 공개 인터페이스.
"""
import uuid

from backend.models import BriefingHeader, BriefingResult, DailySummary, KPIReport, WorkCard


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
    urgent = sum(1 for c in cards if c.urgency_level >= 4)
    total_minutes = sum(c.estimated_minutes for c in cards)

    header = BriefingHeader(
        briefing_id=str(uuid.uuid4()),
        absence_days=absence_days,
        total=len(cards),
        urgent=urgent,
        estimated_minutes=total_minutes,
        contacts_needed=[
            {"person": c.from_person, "reason": c.summary, "channel": c.source}
            for c in cards if c.urgency_level >= 4
        ],
        summary_text=(
            f"{absence_days}일 부재 동안 {len(cards)}건 수신. "
            f"긴급 항목 {urgent}건."
        ),
    )
    # TODO: save_briefing(user_id, result) — TinyDB 구현 후 추가
    return BriefingResult(header=header, cards=cards)
