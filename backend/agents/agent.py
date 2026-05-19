"""
WorkAssistantAgent — 단일 에이전트 진입점.

n8n AI Agent 노드 대응. tool_use 루프로 하위 툴을 선택·실행한다.
Phase 1: 브리핑 파이프라인 직접 실행 + 단순 LLM 채팅.
Phase 2: 완전 tool_use 루프 (현재 chat()에 적용됨).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import anthropic

from backend.config import settings
from backend.models import BriefingResult, WorkCard
from backend.tools.classify import classify_item
from backend.tools.fetch import fetch_messages
from backend.tools.scoring import calculate_urgency
from backend.tools.storage import finalize_briefing
from backend.tools.policy import retrieve_policy
from backend.tools.task_analysis import analyze_task_order
from backend.tools.alarm import trigger_alarm, AlarmChannel
from backend.tools.spell_check import check_spelling
from backend.tools.document_writer import export_cards_to_csv, generate_filename

_SYSTEM = (
    "당신은 직장인의 업무를 돕는 어시스턴트입니다. "
    "수신된 항목을 분석해 긴급도 순으로 정리하고 "
    "지금 바로 처리할 것과 나중에 처리해도 되는 것을 명확히 구분해주세요. "
    "사용자의 채팅 요청에는 간결하고 실용적으로 답변하세요. "
    "필요한 경우 제공된 툴을 적극적으로 활용하세요. "
    "한국어로 작성하고 마크다운 형식을 사용하세요."
)

# ── Tool 정의 (Anthropic tool_use 스펙) ──────────────────────────────────────
# n8n AI Agent에 연결된 각 tool 노드를 그대로 매핑.

TOOLS: list[dict] = [
    {
        "name": "retrieve_policy",
        "description": (
            "회사 내규, 출장비/유류비 정산 기준, 사내 규정 관련 질문에 답할 때 사용합니다. "
            "정책이나 규정 기준이 필요한 경우 이 툴을 호출하세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 규정 키워드 또는 질문"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "retrieve_work_data",
        "description": (
            "메일, Jira 이슈, Slack 메시지, 업로드 문서 등 업무 관련 데이터를 검색할 때 사용합니다. "
            "사용자가 업무 현황, 미처리 이슈, 첨부파일, 문서 내용을 물어볼 때 이 툴을 호출하세요."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색할 업무 내용 키워드"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "analyze_task_order",
        "description": "현재 브리핑 카드를 분석해 처리 순서와 예상 소요시간을 구조화합니다.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "trigger_alarm",
        "description": "마감 임박·긴급 항목에 대해 Slack DM 또는 이메일 알림을 발송합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "알람 대상 WorkCard ID"},
                "message": {"type": "string", "description": "알람 메시지"},
                "channel": {
                    "type": "string",
                    "enum": ["console", "slack", "email"],
                    "description": "발송 채널",
                },
            },
            "required": ["item_id", "message"],
        },
    },
    {
        "name": "check_spelling",
        "description": "텍스트의 맞춤법을 검사하고 교정 결과를 반환합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "맞춤법을 검사할 텍스트"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "export_document",
        "description": "현재 브리핑 카드를 CSV 파일로 내보냅니다. 다운로드 링크를 반환합니다.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


class WorkAssistantAgent:
    """브리핑 + 채팅 요청을 처리하는 단일 에이전트."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._current_cards: list[WorkCard] = []

    # ── 브리핑 파이프라인 ──────────────────────────────────────────────────────

    def run_briefing(self, user_id: str, absence_days: int) -> BriefingResult:
        """fetch → score → classify → finalize 파이프라인."""
        items = []
        for source in ["gmail", "slack", "jira", "calendar"]:
            items += fetch_messages(source, since_days=absence_days)

        cards = []
        for item in items:
            level, breakdown = calculate_urgency(item)
            card = classify_item(item, level, breakdown)
            cards.append(card)

        cards.sort(key=lambda c: c.urgency_level, reverse=True)
        self._current_cards = cards
        return finalize_briefing(cards, absence_days, user_id)

    def run_briefing_simple(self, user_id: str, absence_days: int) -> str:
        """fetch → 단일 LLM 호출 → 마크다운 리포트 반환 (데모용)."""
        items = []
        for source in ["gmail", "slack", "calendar"]:
            items += fetch_messages(source, since_days=absence_days)

        if not items:
            return "수신된 항목이 없습니다."

        prompt = self._build_briefing_prompt(items, absence_days)
        return self._call_llm(prompt)

    # ── 채팅 요청 처리 (tool_use 루프) ───────────────────────────────────────

    def chat(self, prompt: str) -> str:
        """사이드바 채팅 요청을 tool_use 루프로 처리."""
        messages = [{"role": "user", "content": prompt}]

        while True:
            response = self._client.messages.create(
                model=settings.smart_model,
                max_tokens=2048,
                system=_SYSTEM,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            # tool_use 블록 처리
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._run_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    # ── 스케줄 트리거 (n8n 시간 트리거 12/13/18시 대응) ──────────────────────

    def run_scheduled(self, hour: int) -> str:
        """
        n8n 시간 트리거 노드 대응. scheduler.py에서 호출.
        12시: 오전 미처리 항목 리마인드.
        13시: 점심 후 우선순위 재정렬.
        18시: 오늘 처리 현황 요약.
        """
        prompts = {
            12: "오전 미처리 항목을 확인하고 오후 처리 순서를 추천해주세요.",
            13: "점심 후 남은 업무를 긴급도 순으로 재정렬해 알려주세요.",
            18: "오늘 처리한 업무와 미처리 항목을 요약해주세요.",
        }
        prompt = prompts.get(hour, f"{hour}시 업무 현황을 정리해주세요.")
        return self.chat(prompt)

    # ── Tool 실행 디스패처 ────────────────────────────────────────────────────

    def _run_tool(self, name: str, inputs: dict) -> dict:
        """tool_use 블록을 실행하고 결과를 dict로 반환."""
        if name == "retrieve_policy":
            text = retrieve_policy(inputs["query"])
            return {"result": text}

        if name == "retrieve_work_data":
            from backend.services.vector_store import get_store
            docs = get_store("work").retrieve(inputs["query"])
            return {"result": "\n---\n".join(d.content for d in docs) or "관련 업무 데이터 없음"}

        if name == "analyze_task_order":
            if not self._current_cards:
                return {"result": "브리핑 데이터가 없습니다. 먼저 브리핑을 실행해주세요."}
            result = analyze_task_order(self._current_cards)
            return {"summary": result.summary, "groups": [g.label for g in result.groups]}

        if name == "trigger_alarm":
            channel = AlarmChannel(inputs.get("channel", "console"))
            alarm = trigger_alarm(inputs["item_id"], inputs["message"], channel)
            return {"sent": alarm.sent, "channel": alarm.channel}

        if name == "check_spelling":
            return check_spelling(inputs["text"])

        if name == "export_document":
            if not self._current_cards:
                return {"result": "내보낼 브리핑 데이터가 없습니다."}
            filename = generate_filename()
            return {"filename": filename, "card_count": len(self._current_cards)}

        return {"error": f"알 수 없는 툴: {name}"}

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _extract_text(self, response) -> str:
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _build_briefing_prompt(self, items, absence_days: int) -> str:
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

    def _call_llm(self, prompt: str, system: str | None = None) -> str:
        response = self._client.messages.create(
            model=settings.smart_model,
            max_tokens=1024,
            system=system or _SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
