"""
브리핑 파이프라인 오케스트레이터 — 담당 #1.

run_simple : 단일 LLM 호출로 브리핑 리포트 텍스트 반환 (현재 데모용)
run        : fetch → score → classify → finalize 파이프라인 (Week 3 전환 예정)
"""
from datetime import datetime, timezone

import anthropic

from backend.config import settings
from backend.models import BriefingResult
from backend.tools.classify import classify_item
from backend.tools.fetch import fetch_messages
from backend.tools.scoring import calculate_urgency
from backend.tools.storage import finalize_briefing

_SYSTEM = (
    "당신은 직장인의 업무 복귀를 돕는 어시스턴트입니다. "
    "수신된 항목을 분석해 긴급도 순으로 정리하고 "
    "지금 바로 처리할 것과 나중에 처리해도 되는 것을 명확히 구분해주세요. "
    "한국어로 작성하고 마크다운 형식을 사용하세요."
)


# ── 데모용: 단일 LLM 호출 ─────────────────────────────────────────────────────

def run_simple(user_id: str, absence_days: int) -> str:
    """fetch → 프롬프트 구성 → 단일 LLM 호출 → 마크다운 리포트 반환."""
    items = []
    for source in ["gmail", "slack", "calendar"]:
        items += fetch_messages(source, since_days=absence_days)

    if not items:
        return "수신된 항목이 없습니다."

    prompt = _build_prompt(items, absence_days)
    return _call_llm(prompt)


def _build_prompt(items, absence_days: int) -> str:
    now = datetime.now(timezone.utc)
    lines = []
    for i, item in enumerate(items, 1):
        due_str = ""
        if item.due_at:
            diff = (item.due_at - now).total_seconds() / 3600
            due_str = f" | 마감 {'초과' if diff < 0 else f'{diff:.0f}h 후'}"
        lines.append(
            f"{i}. [{item.source.upper()}] {item.from_name} → {item.subject}{due_str}"
        )

    return (
        f"{absence_days}일 부재 동안 수신된 항목 {len(items)}건입니다:\n\n"
        + "\n".join(lines)
        + "\n\n아래 형식으로 복귀 브리핑 리포트를 작성해주세요:\n"
        "## 🔴 지금 당장 처리\n"
        "## 🟡 오늘 안에 처리\n"
        "## 🟢 이번 주 내 처리\n"
        "## 📌 읽기만 하면 됨 (FYI)\n"
        "## 요약\n"
    )


def _call_llm(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.fast_model,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── 파이프라인 (Week 3 tool_use 전환 예정) ────────────────────────────────────

def run(user_id: str, absence_days: int) -> BriefingResult:
    """fetch → score → classify → finalize 파이프라인."""
    items = []
    for source in ["gmail", "slack", "calendar"]:
        items += fetch_messages(source, since_days=absence_days)

    cards = []
    for item in items:
        level, breakdown = calculate_urgency(item)
        card = classify_item(item, level, breakdown)
        cards.append(card)

    cards.sort(key=lambda c: c.urgency_level, reverse=True)
    return finalize_briefing(cards, absence_days, user_id)
