"""
Briefing Agent — 담당 #1.
Anthropic tool_use API로 fetch / scoring / classify / finalize 툴을 자율 조합한다.
파이프라인 순서를 코드에 하드코딩하지 않는다.
"""
from anthropic import AsyncAnthropic

from backend.agents.llm_client import _model
from backend.config import settings
from backend.models import BriefingResult

# ── Tool Registry ─────────────────────────────────────────────────────────────
# LLM이 호출할 수 있는 도구 목록. 스키마만 정의 — 실제 구현은 _dispatch() 참조.

TOOL_REGISTRY = [
    {
        "name": "fetch_messages",
        "description": "지정 소스에서 부재 기간 메시지 수집",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": ["gmail", "slack", "calendar", "jira"]},
                "since_days": {"type": "integer"},
            },
            "required": ["source", "since_days"],
        },
    },
    {
        "name": "score_urgency",
        "description": "수집된 항목에 정량 긴급도 점수 부여 (LLM 미사용)",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["item_ids"],
        },
    },
    {
        "name": "classify_items",
        "description": "긴급도 계산 완료 항목에 액션 타입과 요약 부여 (LLM Fast 1-shot)",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["item_ids"],
        },
    },
    {
        "name": "finalize_briefing",
        "description": "분류 완료 항목으로 브리핑 헤더 생성 및 저장 (LLM Smart)",
        "input_schema": {
            "type": "object",
            "properties": {"absence_days": {"type": "integer"}},
            "required": ["absence_days"],
        },
    },
]


async def _dispatch(tool_name: str, tool_input: dict):
    """Tool 이름 → tools/ 함수 호출 라우팅. 담당 #1이 구현."""
    # TODO: 각 tool_name을 tools/ 함수에 매핑
    #   "fetch_messages"  → tools.fetch.fetch_messages(...)
    #   "score_urgency"   → tools.scoring.score_urgency(...)
    #   "classify_items"  → tools.classify.classify_items(...)
    #   "finalize_briefing" → tools.storage.finalize_briefing(...)
    ...


async def run(user_id: str, absence_days: int) -> BriefingResult:
    """Briefing Agent 진입점. Streamlit에서 직접 호출."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages = [
        {"role": "user", "content": f"사용자 {user_id}의 {absence_days}일 복귀 브리핑을 생성해줘."}
    ]

    while True:
        response = await client.messages.create(
            model=_model("smart"),
            tools=TOOL_REGISTRY,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _dispatch(block.name, block.input)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages += [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": results},
            ]

    # TODO: messages 마지막 응답에서 BriefingResult 추출 후 반환
    ...
