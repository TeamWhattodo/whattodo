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
    source_id: str | None = None   # Gmail: threadId, Slack: channel_id:thread_ts, Jira: issue_key
    status: Literal["pending", "done", "snoozed"] = "pending"
    created_at: datetime
    completed_at: datetime | None = None
    actual_minutes: int | None = None


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
