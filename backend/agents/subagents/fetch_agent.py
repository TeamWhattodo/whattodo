from __future__ import annotations

import json

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

limit: 숫자 명시 시 해당 값, 전체 현황·복귀 브리핑이면 50, 기본 20
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
    items = sorted(items, key=lambda x: x.get("created_at") or "", reverse=True)[:limit]

    structured = [_to_structured(i) for i in items]
    return json.dumps({"total": len(structured), "items": structured}, ensure_ascii=False, default=str), {}


def _urgency_category(level: int) -> str:
    if level >= 7:
        return "urgent"
    if level >= 4:
        return "important"
    return "normal"


def _to_structured(item: dict) -> dict:
    return {
        "source":           item.get("source", ""),
        "from_person":      item.get("from_person") or "",
        "summary":          item.get("summary") or item.get("raw_content", "")[:200],
        "due_at":           item.get("due_at") or "",
        "action_type":      item.get("action_type", "none"),
        "urgency_level":    item.get("urgency_level", 0),
        "urgency_category": _urgency_category(item.get("urgency_level", 0)),
        "status":           item.get("status", ""),
    }
