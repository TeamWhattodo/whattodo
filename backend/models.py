from pydantic import BaseModel
from typing import Literal
from datetime import datetime


class WorkItem(BaseModel):
    id: str
    source: Literal["gmail", "slack", "calendar", "jira", "notion"]
    raw_content: str
    summary: str
    urgency_level: int              # 1~5
    urgency_breakdown: dict = {}    # {"T": 0.78, ...}
    action_type: str                # reply / approve / review / fyi / none
    from_person: str | None = None
    due_at: datetime | None = None
    status: Literal["pending", "done", "snoozed"] = "pending"
    created_at: datetime
    completed_at: datetime | None = None
    actual_minutes: int | None = None


class WorkCard(BaseModel):          # UI 렌더링 전용
    id: str
    source: str
    summary: str
    urgency_level: int
    action_type: str
    from_person: str | None = None
    estimated_minutes: int = 10
    due_at: datetime | None = None
    status: str = "pending"


class BriefingResult(BaseModel):
    briefing_id: str
    stats: dict                     # total, urgent, fyi, estimated_minutes
    sections: dict                  # immediate, today, fyi
    summary_text: str


class ReceiptItem(BaseModel):
    date: str
    merchant: str
    amount: int
    category: str
    memo: str | None = None


class ExpenseReport(BaseModel):
    id: str
    created_at: datetime
    report_type: str
    items: list[ReceiptItem]
    total_amount: int
    xlsx_path: str | None = None
    pdf_path: str | None = None
