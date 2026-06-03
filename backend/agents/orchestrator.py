from __future__ import annotations

import json
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import add_messages
from langgraph.types import Send

from backend.agents.llm_client import get_llm


# ── State ──────────────────────────────────────────────────────────────────────

import operator

def merge_results(left: dict, right: dict) -> dict:
    if not left: left = {}
    if not right: right = {}
    return {**left, **right}

def merge_bool(left: bool, right: bool) -> bool:
    return left or right

class WhatToDoState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # 대화 이력 자동 누적
    user_input: str
    intent: str               # briefing | report | action | search | chat
    work_items: list[dict]
    results: Annotated[dict, merge_results]
    error: str | None
    retry_count: int          # output_validator 재시도 횟수 (max 2)
    has_write_output: Annotated[bool, merge_bool]    # write_* 호출 여부 → validator 진입 조건
    user_preferences: dict    # Phase 3: memory 레이어


# ── Harnessing ① intent 보정 ───────────────────────────────────────────────────

_VALID_INTENTS: set[str] = {"briefing", "report", "action", "search", "chat"}

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "briefing": ["정리", "브리핑", "쌓인", "복귀", "출근", "현황", "가져와", "수집"],
    "report":   ["리포트", "정산", "결산", "KPI", "작성"],
    "action":   ["초안", "답장", "완료", "처리", "잡아", "삭제", "생성", "캘린더"],
    "search":   ["규정", "한도", "찾아", "검색", "얼마", "일정", "스레드", "항목", "내용"],
}

_BRIEFING_SOURCES = ["slack", "슬랙", "슬렉", "jira", "지라", "notion", "노션",
                     "gmail", "메일", "이메일",
                     "calendar", "캘린더", "스케줄", "스케쥴", "스캐쥴", "스캐줄"]


def validate_intent(intent: str, user_input: str) -> str:
    # 소스명 + 정리/브리핑/현황/조회 동사 패턴은 briefing으로 강제
    u = user_input.lower()
    has_source = any(s in u for s in _BRIEFING_SOURCES)
    has_briefing_verb = any(w in u for w in ["정리", "브리핑", "현황", "요약",
                                              "알려줘", "보여줘", "꺼내줘", "조회"])
    if has_source and has_briefing_verb:
        return "briefing"

    matched = [k for k, words in _INTENT_KEYWORDS.items()
               if any(w in user_input for w in words)]
    if len(matched) > 1 and "," not in intent:
        return ",".join(matched)
    return intent


# ── Harnessing ② constraint check ─────────────────────────────────────────────

_CONSTRAINTS: dict[str, dict] = {
    "score_urgency":  {"requires": ["fetch_emails", "fetch_slack_messages",
                                    "fetch_calendar_events", "fetch_jira_issues"]},
    "classify_items": {"requires": ["score_urgency"]},
    "write_report":   {"requires": ["classify_items"]},
    "write_draft":    {"requires": ["get_item_thread"]},
}


def check_constraint(tool_name: str, called_tools: list[str]) -> tuple[bool, str]:
    c = _CONSTRAINTS.get(tool_name)
    if not c:
        return True, ""
    if not any(t in called_tools for t in c["requires"]):
        return False, f"{tool_name} 실행 불가: {c['requires']} 중 하나가 먼저 필요"
    return True, ""


# ── 시스템 프롬프트 ─────────────────────────────────────────────────────────────

_ORCHESTRATOR_SYSTEM = """\
당신은 업무 요청을 분류해 적합한 SubAgent에 라우팅합니다.

분류 기준:
- briefing : 업무 현황 정리·브리핑·요약. Gmail·Slack·Jira·Notion·캘린더 등 소스별 업무 정리 포함.
             예) "지라 업무 정리", "슬랙 정리해줘", "쌓인 업무 브리핑", "메일 현황 알려줘"
- report   : 정산 리포트, 일간 결산, 주간 KPI, 파일 분석
- action   : 답장 초안 작성, 항목 완료·스누즈, 캘린더 일정 생성·삭제, Gmail/Slack 발송·삭제
- search   : 특정 키워드·조건으로 데이터 검색. 사내 규정 조회, 과거 항목 검색, 영수증 검증.
             예) "OOO 찾아줘", "OOO 검색해줘", "규정 알려줘"
- chat     : 위에 해당하지 않는 일반 질문

복합 의도(예: 영수증 검증 + 규정 조회)는 쉼표로 구분해 반환하세요.
예: "report,search"

intent 단어만 반환하세요. 설명 없이.\
"""

_VERIFY_PROMPT = """\
다음 기준으로 출력을 평가하세요.
1. 사용자 요청에 직접 답했는가
2. 누락된 핵심 정보가 없는가
3. 사실 오류나 모순이 없는가
JSON만 반환: {{"is_sufficient": bool, "feedback": "미흡 시만 기재"}}\
"""

_REGENERATE_PROMPT = """\
아래 출력이 다음 이유로 미흡합니다: {feedback}

사용자 요청: {user_input}

기존 출력을 feedback을 반영해 개선하세요. 개선된 텍스트만 반환하세요.\
"""


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────

def _get_result_text(results: dict) -> str:
    """results dict에서 최종 응답 텍스트를 모두 추출하여 병합한다."""
    texts = []
    for key in ("briefing", "report", "action", "search", "chat"):
        r = results.get(key)
        if not r:
            continue
        if isinstance(r, dict):
            text = r.get("text", "")
            if text:
                texts.append(text)
        elif isinstance(r, str):
            texts.append(r)
    return "\n\n---\n\n".join(texts)


# ── Nodes ──────────────────────────────────────────────────────────────────────

def intent_classifier(state: WhatToDoState) -> WhatToDoState:
    """LLM Smart — intent 분류 전담. 이전 대화 맥락을 참고한다."""
    llm = get_llm("smart")
    history = (state.get("messages") or [])[:-1]  # 현재 HumanMessage 제외
    recent = history[-6:]  # 최근 3턴 (human+ai 각 1개씩 × 3)

    llm_intent = llm.invoke([
        SystemMessage(content=_ORCHESTRATOR_SYSTEM),
        *recent,
        HumanMessage(content=state["user_input"]),
    ]).content.strip().lower()
    parts = [p.strip() for p in llm_intent.split(",")]
    clean_intent = ",".join(p for p in parts if p in _VALID_INTENTS) or "chat"
    intent = validate_intent(clean_intent, state["user_input"])
    return {"intent": intent}


def collect_results(state: WhatToDoState) -> WhatToDoState:
    """SubAgent 결과 병합 + action_type · urgency 기준 정렬."""
    _ACTION_PRIORITY = {"reply": 5, "approve": 4, "review": 3, "fyi": 2, "none": 1}

    all_items: list[dict] = []
    for agent_result in state.get("results", {}).values():
        if isinstance(agent_result, list):
            all_items.extend(agent_result)
        elif isinstance(agent_result, dict) and "work_items" in agent_result:
            all_items.extend(agent_result["work_items"])

    all_items.sort(key=lambda x: (
        -_ACTION_PRIORITY.get(x.get("action_type", "none"), 0),
        -x.get("urgency_level", 0),
    ))
    return {"work_items": all_items}


def output_validator(state: WhatToDoState) -> WhatToDoState:
    """write_* 출력 검증·재생성 후 최종 응답을 messages에 추가한다."""
    results = state.get("results", {})
    retry = state.get("retry_count", 0)

    if state.get("has_write_output"):
        llm = get_llm("fast")
        while retry < 2:
            results_text = _get_result_text(results)
            if not results_text:
                break
                
            verdict_raw = llm.invoke([
                SystemMessage(content=_VERIFY_PROMPT),
                HumanMessage(content=f"사용자 요청: {state['user_input']}\n\n출력:\n{results_text}"),
            ]).content.strip()

            try:
                verdict = json.loads(verdict_raw)
            except Exception:
                break

            if verdict.get("is_sufficient", True):
                break

            feedback = verdict.get("feedback", "")
            improved = llm.invoke([
                HumanMessage(content=_REGENERATE_PROMPT.format(
                    feedback=feedback,
                    user_input=state["user_input"],
                ) + f"\n\n기존 출력:\n{results_text}"),
            ]).content.strip()

            write_key = next(
                (k for k in results if k in ("briefing", "report", "action")), None
            )
            if write_key:
                results = {**results, write_key: {**results[write_key], "text": improved}}

            retry += 1

    # 최종 응답을 대화 이력에 추가 (add_messages reducer가 누적 처리)
    final_text = _get_result_text(results)
    new_state = {"results": results, "retry_count": retry}
    if final_text:
        new_state["messages"] = [AIMessage(content=final_text)]
    return new_state


def general_chat(state: WhatToDoState) -> WhatToDoState:
    """tool 없는 단순 Q&A. 전체 대화 이력을 LLM에 전달한다."""
    messages = state.get("messages") or [HumanMessage(content=state["user_input"])]
    response = get_llm("fast").invoke(messages).content
    return {"results": {"chat": {"text": response}}}


# ── Routing ────────────────────────────────────────────────────────────────────

def route_by_intent(state: WhatToDoState):
    intents = [i.strip() for i in state["intent"].split(",")]
    if len(intents) > 1:
        return [Send(i, state) for i in intents]
    return intents[0]


# ── Supervisor ─────────────────────────────────────────────────────────────────

_SUPERVISOR_SYSTEM = """\
당신은 업무 관리 AI 어시스턴트입니다. 사용자의 요청을 분석하여 적합한 도구를 순서에 맞게 호출합니다.

## 도구 호출 규칙

1. 복귀 브리핑·업무 현황·소스별 항목 조회
   → fetch_agent(request)          — DB에서 항목 조회
   → briefing_agent(context=fetch결과의 content, request=원래요청)  — 마크다운 포맷

2. 정산·KPI·영수증 등 파일 export
   → report_agent(request)          — xlsx/pdf 파일 생성

3. 특정 항목·규정·스레드 검색
   → search_agent(query)

4. 답장 초안·발송·Jira·Notion·캘린더 조작
   → action_agent(request)
   (실행 전 사용자 확인이 자동으로 요청됩니다)

5. 일반 대화·인사·단순 질문
   → 도구 없이 직접 응답

## 복합 요청 처리
- "브리핑하고 KPI 리포트도 만들어줘" → fetch_agent → briefing_agent → report_agent(KPI)
- "메일 확인하고 답장 써줘" → fetch_agent → briefing_agent → action_agent

## 도구 응답 형식
모든 도구는 JSON을 반환합니다:
- status: "success" | "error" | "cancelled" | "not_found"
- agent: 도구 이름
- content: 사용자에게 전달할 실제 내용

도구 응답에서 반드시 content 필드를 사용해 사용자에게 답하세요.
status가 "error"이면 실패 사실을 간결하게 알리고, 재시도를 자동으로 하지 마세요.

항상 한국어로 응답하세요.\
"""


def build_supervisor():
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver
    from backend.agents.subagents.agent_tools import SUPERVISOR_TOOLS

    def _trim_hook(state: dict) -> dict:
        """LLM에 전달하는 메시지를 최근 20개로 제한한다. checkpointer 저장 내용은 유지."""
        msgs = state.get("messages", [])
        if len(msgs) > 20:
            return {"messages": msgs[-20:]}
        return {}

    return create_react_agent(
        model=get_llm("fast"),
        tools=SUPERVISOR_TOOLS,
        prompt=_SUPERVISOR_SYSTEM,
        pre_model_hook=_trim_hook,
        checkpointer=MemorySaver(),
    )
