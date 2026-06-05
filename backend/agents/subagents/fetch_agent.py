from __future__ import annotations

import json
from datetime import datetime
from math import ceil, exp

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm_client import get_llm
from backend.tools.storage import search_items

_PARAM_EXTRACT_SYSTEM = """\
사용자 요청에서 DB 조회 파라미터를 추출하세요.
JSON만 반환하세요: {"source": "", "limit": 20, "status": "", "query": ""}

source: "gmail" | "slack" | "jira" | "notion" | "calendar" | "" (전체)
  - 메일·이메일·gmail → "gmail"
  - 슬랙·slack → "slack"
  - 지라·jira → "jira"
  - 노션·notion → "notion"
  - 캘린더·일정·calendar → "calendar"
  - 전체·모든·명시 없음·복귀·브리핑 → ""

status: "pending" | "done" | "" (전체)
  - 미완료·대기·긴급·쌓인 → "pending"
  - 완료 → "done"
  - 명시 없음 → ""

limit: 숫자 명시 시 해당 값, 기본 50 (상위 20개로 최종 압축됨)
query: 특정 키워드 검색 시만 입력, 없으면 ""\
"""


async def run(user_input: str, user_id: int = 1) -> tuple[str, dict]:
    llm = get_llm("fast")
    raw = (await llm.ainvoke([
        SystemMessage(content=_PARAM_EXTRACT_SYSTEM),
        HumanMessage(content=user_input),
    ])).content.strip()

    try:
        params = json.loads(raw)
    except Exception:
        params = {}

    source = params.get("source") or None
    status = params.get("status") or None
    limit = int(params.get("limit") or 20)
    query = params.get("query") or ""

    items = search_items(user_id=user_id, query=query, status=status, source=source)
    items = items[:limit]

    structured = [_to_structured(i) for i in items]

    # 마감일 있는 것 우선, 그 다음 긴급도 순 정렬 후 상위 20개만 반환
    _ORDER = {"urgent": 0, "important": 1, "normal": 2}
    structured.sort(key=lambda x: (
        0 if x.get("deadline") else 1,
        _ORDER.get(x.get("urgency_category", "normal"), 2),
        -x.get("urgency_level", 1),
    ))
    structured = structured[:20]

    return json.dumps({"total": len(structured), "items": structured}, ensure_ascii=False, default=str), {}


_URGENT_KEYWORDS    = ["긴급", "마감 초과", "즉시", "critical", "urgent", "[긴급]"]
_IMPORTANT_KEYWORDS = ["승인 요청", "검토 요청", "리뷰", "review", "배포", "마감"]


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _calc_level(deadline_str: str, created_at_str: str) -> int:
    """deadline 또는 경과 시간 기반으로 urgency_level(1~10)을 동적 계산한다."""
    now = datetime.now()
    deadline_dt = _parse_dt(deadline_str)
    created_dt  = _parse_dt(created_at_str) or now

    if deadline_dt:
        hours_left = (deadline_dt - now).total_seconds() / 3600
        t = 1.0 if hours_left <= 0 else 1 - exp(-3 / max(hours_left, 0.5))
    else:
        hours_elapsed = (now - created_dt).total_seconds() / 3600
        t = min(hours_elapsed / 72, 0.6)

    return max(1, ceil(t * 10))


def _urgency_category(level: int, summary: str = "") -> str:
    if level >= 7:
        return "urgent"
    if level >= 4:
        return "important"
    # 시간 기반 점수가 낮아도 키워드로 상향
    if summary:
        s = summary.lower()
        if any(k in s for k in _URGENT_KEYWORDS):
            return "urgent"
        if any(k in s for k in _IMPORTANT_KEYWORDS):
            return "important"
    return "normal"


def _to_structured(item: dict) -> dict:
    summary  = item.get("summary") or item.get("raw_content", "")[:200]
    deadline = item.get("deadline") or item.get("due_at") or ""
    level    = _calc_level(deadline, item.get("created_at", ""))
    return {
        "source":           item.get("source", ""),
        "from_person":      item.get("from_person") or "",
        "summary":          summary,
        "deadline":         deadline,
        "action_type":      item.get("action_type", "none"),
        "urgency_level":    level,
        "urgency_category": _urgency_category(level, summary),
        "urgency_reason":   item.get("urgency_reason") or "",
        "status":           item.get("status", ""),
    }
