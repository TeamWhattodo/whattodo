from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm_client import get_llm

logger = logging.getLogger(__name__)

_SYSTEM = """\
업무 항목 목록에서 마감시간과 긴급 사유를 추출하세요.
JSON 배열만 반환하세요:
[{"id": "...", "deadline": "YYYY-MM-DDTHH:MM:SS 또는 null", "urgency_reason": "한 줄 또는 null"}]
deadline: 텍스트에 명시된 날짜·시각. created_at을 기준으로 "내일", "이번 주 금요일" 등 상대 날짜를 절대 날짜로 변환하라. 날짜 언급 없으면 null
urgency_reason: 승인 요청·배포·마감 초과 등 긴급 사유. 없으면 null\
"""

_BATCH_SIZE = 30


def extract_deadlines(items: list[dict]) -> list[dict]:
    """due_at·deadline이 없는 항목만 LLM으로 deadline/urgency_reason을 추출한다."""
    targets = [i for i in items if not i.get("due_at") and not i.get("deadline")]
    if not targets:
        return items

    result_map: dict[str, dict] = {}
    for i in range(0, len(targets), _BATCH_SIZE):
        batch = targets[i : i + _BATCH_SIZE]
        result_map.update(_call_llm(batch))

    for item in items:
        r = result_map.get(item["id"])
        if not r:
            continue
        if r.get("deadline"):
            item["deadline"] = r["deadline"]
        if r.get("urgency_reason"):
            item["urgency_reason"] = r["urgency_reason"]

    return items


def _call_llm(batch: list[dict]) -> dict[str, dict]:
    payload = [
        {
            "id": i["id"],
            "created_at": str(i.get("created_at", "")),
            "text": ((i.get("summary") or "") + " " + (i.get("raw_content") or "")[:300]).strip(),
        }
        for i in batch
    ]
    try:
        raw = get_llm("fast").invoke(
            [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
            config={"callbacks": []},  # LangSmith 트레이싱 제외 (백그라운드 ingestion)
        ).content.strip()
        results = json.loads(raw)
        return {r["id"]: r for r in results if isinstance(r, dict) and "id" in r}
    except Exception as e:
        logger.warning(f"deadline 추출 실패: {e}")
        return {}
