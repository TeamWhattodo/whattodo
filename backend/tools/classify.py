import json
from backend.agents.llm_client import complete


CLASSIFY_SYSTEM = """
아래 업무 항목을 분석해 JSON으로만 반환하라. 다른 텍스트 없이 JSON만.

{
  "action_type": "reply | approve | review | fyi | none",
  "summary": "1~2줄 한국어 요약",
  "estimated_minutes": 소요 예상 시간(정수)
}
"""


def classify_one(item: dict) -> dict:
    prompt = f"항목 내용: {item['raw_content']}\n발신자: {item.get('from_person', '알 수 없음')}"
    try:
        raw = complete(prompt, tier="fast", system=CLASSIFY_SYSTEM)
        parsed = json.loads(raw.strip())
        item.update(parsed)
    except Exception:
        item["action_type"]       = "review"
        item["summary"]           = item["raw_content"][:50]
        item["estimated_minutes"] = 10
    return item


def classify_items(items: list[dict]) -> list[dict]:
    """
    ScoredItem[] → action_type + summary + estimated_minutes 추가 후 반환
    LLM Fast 티어 사용.
    """
    return [classify_one(item) for item in items]


def filter_items(items: list[dict], min_urgency: int = 3) -> list[dict]:
    """urgency_level >= min_urgency 인 항목만 반환. LLM 미사용."""
    return [i for i in items if i.get("urgency_level", 0) >= min_urgency]


def group_by_topic(items: list[dict]) -> dict:
    """action_type별로 그룹핑. LLM Fast 티어 사용 예정. Week 2에 구현."""
    # TODO (#3): LLM으로 토픽 클러스터링 구현
    groups: dict[str, list] = {}
    for item in items:
        key = item.get("action_type", "none")
        groups.setdefault(key, []).append(item)
    return groups


if __name__ == "__main__":
    test = [{
        "id": "test_001",
        "raw_content": "김대표: 계약서 서명 요청드립니다.",
        "from_person": "김대표",
        "urgency_level": 5,
        "source": "gmail",
    }]
    result = classify_items(test)
    print(result[0]["action_type"], result[0]["summary"])
