"""
규칙 기반 긴급도 계산 (LLM 없음)
수집 후 DB 저장 전에 실행.
"""
from datetime import datetime, timezone
from backend.tools.storage import search_items


def score_urgency(item: dict) -> tuple[int, str]:
    """WorkItem dict를 받아 (urgency_level 1~5, reason) 반환."""
    score = 0
    reasons = []

    now = datetime.now(timezone.utc)

    # 1. 마감 임박도
    deadline = item.get("deadline") or item.get("due_at")
    if deadline:
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
            except Exception:
                deadline = None
        if deadline:
            hours_left = (deadline - now).total_seconds() / 3600
            if hours_left <= 0:
                score += 3; reasons.append("마감 초과")
            elif hours_left <= 6:
                score += 3; reasons.append("6시간 이내 마감")
            elif hours_left <= 24:
                score += 2; reasons.append("24시간 이내 마감")
            elif hours_left <= 48:
                score += 1; reasons.append("48시간 이내 마감")

    # 2. 발신자 연락 빈도
    from_person = item.get("from_person")
    if from_person:
        existing = search_items(query=from_person, source=item.get("source"))
        count = len(existing)
        if count >= 3:
            score += 2; reasons.append(f"동일 발신자 {count}회 연락")
        elif count >= 2:
            score += 1; reasons.append(f"동일 발신자 {count}회 연락")

    # 3. 미응답 기간
    created_at = item.get("created_at")
    if created_at:
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except Exception:
                created_at = None
        if created_at:
            age_hours = (now - created_at).total_seconds() / 3600
            if age_hours > 48:
                score += 2; reasons.append("48시간 이상 미응답")
            elif age_hours > 24:
                score += 1; reasons.append("24시간 이상 미응답")

    # 4. 소스 가중치
    source = item.get("source", "")
    if source == "jira":
        raw = item.get("raw_content", "")
        if "blocker" in raw.lower() or "highest" in raw.lower():
            score += 2; reasons.append("Jira Blocker/Highest")
        elif "high" in raw.lower():
            score += 1; reasons.append("Jira High")
    elif source in ("gmail", "slack"):
        score += 1

    # 5. 키워드
    text = (item.get("summary", "") + " " + item.get("raw_content", "")).lower()
    if any(k in text for k in ["긴급", "urgent", "asap", "[긴급]", "즉시"]):
        score += 1; reasons.append("긴급 키워드")

    # 점수 → 레벨 변환
    if score >= 8:
        level = 5
    elif score >= 6:
        level = 4
    elif score >= 4:
        level = 3
    elif score >= 2:
        level = 2
    else:
        level = 1

    reason = ", ".join(reasons) if reasons else "일반"
    return level, reason
