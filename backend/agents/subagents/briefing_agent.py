from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm_client import get_llm

_BRIEFING_SYSTEM = """\
아래는 Python이 urgency_category 기준으로 분류하고 필드를 매핑한 업무 브리핑 초안입니다.
이 구조를 바탕으로 자연스러운 한국어 업무 브리핑을 작성하세요.

규칙:
- 긴급·중요·일반 섹션 구분과 마크다운 테이블 형식을 유지하세요
- 출처·발신자·내용·마감시간 열은 빠뜨리지 마세요
- "-"인 필드는 그대로 "-"로 표시하세요
- 항목을 임의로 추가하거나 생략하지 마세요
- 섹션이 없으면 헤더째 생략하세요\
"""


def _extract_items_from(data: object) -> list[dict] | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # _wrap() 포맷: {"status": ..., "content": "{\"items\": [...]}"}
        if "content" in data:
            try:
                inner = json.loads(data["content"])
                if isinstance(inner, dict):
                    return inner.get("items", [])
                if isinstance(inner, list):
                    return inner
            except Exception:
                pass
        if "items" in data:
            return data["items"]
    return None


def _parse_items(context: str) -> list[dict]:
    # 직접 JSON 파싱 시도
    try:
        result = _extract_items_from(json.loads(context))
        if result is not None:
            return result
    except Exception:
        pass

    # "[수집 데이터]\n{json}\n\n[요청]\n..." 래핑 형식
    marker, end_marker = "[수집 데이터]\n", "\n\n[요청]"
    start = context.find(marker)
    if start != -1:
        start += len(marker)
        end = context.find(end_marker, start)
        chunk = context[start:end].strip() if end != -1 else context[start:].strip()
        try:
            result = _extract_items_from(json.loads(chunk))
            if result is not None:
                return result
        except Exception:
            pass

    return []


def _fmt(val: object, max_len: int = 80) -> str:
    if not val:
        return "-"
    s = str(val)
    if "T" in s:
        s = s.replace("T", " ").split(".")[0]
    s = s.strip()
    return (s[:max_len] + "…") if len(s) > max_len else s or "-"


def _format_briefing(items: list[dict]) -> str:
    if not items:
        return "## 📋 업무 브리핑\n\n현재 처리 중인 업무가 없습니다."

    buckets: dict[str, list] = {"urgent": [], "important": [], "normal": []}
    for item in items:
        bucket = buckets.get(item.get("urgency_category", "normal"), buckets["normal"])
        bucket.append(item)

    header = "| 출처 | 발신자 | 내용 | 마감시간 |\n|------|--------|------|----------|"
    sections = []
    for emoji, label, key in [("🔴", "긴급", "urgent"), ("🟡", "중요", "important"), ("🟢", "일반", "normal")]:
        group = buckets[key]
        if not group:
            continue
        rows = "\n".join(
            f"| {_fmt(i.get('source'))} | {_fmt(i.get('from_person'))} "
            f"| {_fmt(i.get('summary'), 80)} | {_fmt(i.get('deadline'))} |"
            for i in group
        )
        sections.append(f"### {emoji} {label}\n{header}\n{rows}")

    return "## 📋 업무 브리핑\n\n" + "\n\n".join(sections)


async def run(context: str) -> tuple[str, list[dict]]:
    items = _parse_items(context)
    structured = _format_briefing(items)
    text = (await get_llm("fast").ainvoke([
        SystemMessage(content=_BRIEFING_SYSTEM),
        HumanMessage(content=structured),
    ])).content.strip()
    return text, []
