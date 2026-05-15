"""
브리핑 파이프라인 오케스트레이터 — 담당 #1.
fetch → score → classify → finalize 순서로 직접 호출한다.
Week 3에서 tool_use 에이전트 루프로 전환 예정.
"""
from backend.models import BriefingResult
from backend.tools.classify import classify_item
from backend.tools.fetch import fetch_messages
from backend.tools.scoring import calculate_urgency
from backend.tools.storage import finalize_briefing


def run(user_id: str, absence_days: int) -> BriefingResult:
    """브리핑 파이프라인 진입점. Streamlit에서 직접 호출."""
    # 1. 수집
    items = []
    for source in ["gmail", "slack", "calendar"]:
        items += fetch_messages(source, since_days=absence_days)

    # 2. 긴급도 계산 (T 신호) + 3. 분류 (rule-based → LLM 순)
    cards = []
    for item in items:
        level, breakdown = calculate_urgency(item)
        card = classify_item(item, level, breakdown)
        cards.append(card)

    cards.sort(key=lambda c: c.urgency_level, reverse=True)

    # 4. 브리핑 헤더 생성 + 저장
    return finalize_briefing(cards, absence_days, user_id)
