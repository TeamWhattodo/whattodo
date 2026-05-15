"""
공유 Pydantic 모델 — Week 1에 전원 합의 후 확정.
커넥터(#2, #3), 툴(#4, #5), 에이전트(#1), UI(#6) 모두 이 파일을 참조한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
import uuid


class WorkItem(BaseModel):
    """커넥터가 수집한 원시 항목. scoring 툴 입력."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["gmail", "slack", "calendar", "jira"]
    raw_id: str
    from_email: str
    from_name: str
    subject: str
    body_snippet: str
    received_at: datetime
    due_at: Optional[datetime] = None
    thread_id: Optional[str] = None
    channel: Optional[str] = None


class WorkCard(BaseModel):
    """scoring + classify 완료 항목. Streamlit UI 계약."""
    id: str
    source: Literal["gmail", "slack", "calendar", "jira"]
    summary: str
    urgency_level: int                   # 1~5
    urgency_breakdown: dict              # {"T": 0.78, "A": 0.80, ...}
    action_type: Literal["reply", "approve", "review", "fyi", "none"]
    from_person: str
    received_at: datetime
    estimated_minutes: int
    due_at: Optional[datetime] = None
    status: Literal["pending", "done", "snoozed"] = "pending"


class BriefingHeader(BaseModel):
    briefing_id: str
    absence_days: int
    total: int
    urgent: int
    estimated_minutes: int
    contacts_needed: list[dict]          # [{"person": str, "reason": str, "channel": str}]
    summary_text: str


class BriefingResult(BaseModel):
    """Briefing Agent가 반환하는 최종 결과."""
    header: BriefingHeader
    cards: list[WorkCard]


class DailySummary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str                            # "YYYY-MM-DD"
    completion_rate: float
    avg_response_minutes: float
    overdue_count: int
    by_source: dict
    carryover_items: list[str]


class KPIReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    period: str = "weekly"
    period_start: str
    period_end: str
    aggregated: dict
    vs_prev_week: dict
    narrative: str
    recommendations: list[str]
