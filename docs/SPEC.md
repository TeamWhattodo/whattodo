# WhatToDo — 기술 명세 (SPEC)

## 1. 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 프론트엔드 | **Streamlit** | 전 Phase 고정. 혼합형 UI (카드 + 채팅 사이드바) |
| AI | **Anthropic SDK** | claude-sonnet(Smart) / claude-haiku(Fast) |
| DB | **TinyDB** | JSON 파일 기반. Phase 2+에서 PostgreSQL 교체 가능 |
| 스케줄러 | **APScheduler** | 일간 결산·KPI 크론 (Phase 2) |
| HTTP 클라이언트 | **httpx** | async, OAuth API 호출 |
| OAuth | **authlib** | Gmail, Slack, Jira |
| 백엔드 | **FastAPI** | MVP: OAuth 콜백 수신 전용 |
| 패키지 관리 | **uv** | |

> **FastAPI 역할 (MVP)**: Gmail·Slack OAuth 리디렉션 콜백 수신만 담당. 그 외 파이프라인은 Streamlit이 백엔드 모듈을 직접 import해 호출한다. HTTP 레이어 없이 함수 호출로 처리.

---

## 2. 디렉토리 구조

```
whattodo/
├── app.py                        # Streamlit 진입점 (혼합형 레이아웃)
├── pages/
│   ├── onboarding.py             # 최초 1회 컨텍스트 설정
│   ├── briefing.py               # 복귀 브리핑 카드·체크리스트
│   ├── daily_summary.py          # 일간 결산 (Phase 2)
│   └── kpi_report.py             # KPI 리포트 (Phase 2)
│
├── backend/
│   ├── main.py                   # FastAPI (OAuth 콜백 + health)
│   ├── config.py                 # pydantic-settings 환경 변수
│   ├── models.py                 # ★ 공유 Pydantic 모델 (Week 1 확정)
│   ├── mock_data.py              # UI 독립 개발용 샘플 데이터
│   ├── scheduler.py              # APScheduler 크론 (Phase 2)
│   │
│   ├── routers/
│   │   └── auth.py               # OAuth 콜백 수신
│   │
│   ├── tools/                    # ★ 순수 함수. "다음 뭘 할지" 결정 안 함.
│   │   ├── __init__.py
│   │   ├── fetch.py              # fetch_emails / fetch_slack / fetch_calendar
│   │   ├── scoring.py            # score_urgency (LLM 없음)
│   │   ├── classify.py           # classify_items (LLM Fast 1-shot)
│   │   ├── write_report.py       # write_report (LLM Smart 1-shot)
│   │   ├── write_draft.py        # write_draft (LLM Smart 1-shot)
│   │   ├── update_status.py      # update_item_status (LLM 없음)
│   │   ├── search_items.py       # search_past_items (LLM 없음)
│   │   ├── compute_stats.py      # compute_daily_stats / compute_kpi (LLM 없음)
│   │   ├── parse_billing.py      # parse_billing_data (LLM 없음)
│   │   └── rag.py                # search_company_docs (Phase 2, ChromaDB)
│   │
│   ├── agents/                   # ★ LLM + tool_use 루프. 다음 tool 스스로 선택.
│   │   ├── tool_registry.py      # TOOL_REGISTRY 정의 + _dispatch
│   │   ├── runner.py             # ReAct 루프 핵심 (tool_use 루프)
│   │   ├── prompts.py            # 시스템 프롬프트 + tool 패턴 가이드
│   │   └── llm_client.py         # Provider 추상화 (Anthropic / OpenAI)
│   │
│   ├── connectors/               # 외부 API 클라이언트. tools/fetch.py에서 호출.
│   │   ├── base.py
│   │   ├── gmail.py
│   │   ├── slack.py
│   │   ├── calendar.py
│   │   └── jira.py               # Phase 2
│   │
│   └── db/
│       ├── store.py              # TinyDB 래퍼
│       └── data/
│           ├── work_items.json
│           ├── briefings.json
│           ├── daily_summaries.json
│           └── user_profile.json
│
└── docs/
    ├── PLANNING.md
    ├── SPEC.md
    └── WORKFLOW.md
```

---

## 3. 공유 데이터 스키마 (Week 1 확정 필수)

> **팀장 주도로 Week 1 내 확정. 전원 이 스키마를 출력 포맷으로 준수.**
> 확정 전까지 각 담당자는 mock_data.py의 샘플 데이터로 독립 개발.

```python
# backend/models.py
from pydantic import BaseModel
from typing import Literal
from datetime import datetime, date

# ── 핵심 데이터 단위 ──────────────────────────────────────────
class WorkItem(BaseModel):
    id: str
    source: Literal["gmail", "slack", "calendar", "jira", "notion"]
    raw_content: str
    summary: str                    # classify 툴이 채움
    urgency_level: int              # 1~5. score 툴이 채움
    urgency_breakdown: dict         # {"T": 0.78, ...}
    action_type: Literal["reply", "approve", "review", "fyi", "none"]
    due_at: datetime | None
    from_person: str | None
    status: Literal["pending", "done", "snoozed"]
    created_at: datetime
    completed_at: datetime | None
    actual_minutes: int | None

# ── UI 렌더링 전용 (WorkItem 경량화) ──────────────────────────
class WorkCard(BaseModel):
    id: str
    source: str
    summary: str
    urgency_level: int
    action_type: str
    from_person: str
    estimated_minutes: int
    due_at: datetime | None
    status: str

# ── 브리핑 결과 ───────────────────────────────────────────────
class BriefingResult(BaseModel):
    briefing_id: str
    absence_days: int
    stats: dict                     # total, urgent, fyi, estimated_minutes
    sections: dict                  # immediate[], today[], this_week[], fyi[]
    contacts_needed: list[dict]     # [{person, reason, channel}]
    summary_text: str

# ── 일간 결산 (Phase 2) ───────────────────────────────────────
class DailyStats(BaseModel):
    total_assigned: int
    total_completed: int
    completion_rate: float
    avg_response_minutes: float
    overdue_count: int
    by_source: dict[str, int]
    by_action_type: dict[str, int]
    estimated_minutes: int
    actual_minutes: int

class DailySummary(BaseModel):
    id: str
    date: date
    completed_items: list[WorkCard]
    carried_over_items: list[WorkCard]
    stats: DailyStats
    narrative: str

# ── KPI 리포트 (Phase 2) ─────────────────────────────────────
class KPIAggregated(BaseModel):
    avg_completion_rate: float
    avg_response_minutes: float
    overdue_ratio: float
    busiest_source: str
    carryover_trend: list[int]
    total_items_processed: int

class KPIReport(BaseModel):
    id: str
    period: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    aggregated: KPIAggregated
    vs_prev_period: dict
    narrative: str
    recommendations: list[str]
```

---

## 4. Agent + Tool 구조

### 4-1. Tool vs Agent 구분 원칙

"다음에 뭘 할지 결정하지 않으면 Tool이다."

| 구분 | 판별 기준 |
|---|---|
| **Tool** | 입력 → 출력만. LLM 루프 없음. `tools/` 디렉토리. 단독 테스트 가능. |
| **Agent** | LLM의 `tool_use`를 통해 다음 tool을 스스로 선택. 루프 있음. `agents/` 디렉토리. |

### 4-2. TOOL_REGISTRY

에이전트가 호출할 수 있는 전체 tool 목록. 새 tool 추가 시 에이전트 로직은 건드리지 않는다.

```python
# backend/agents/tool_registry.py
from dataclasses import dataclass
from typing import Callable, Any
import json

@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., Any]

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def to_anthropic_spec(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def execute(self, name: str, inputs: dict) -> str:
        if name not in self._tools:
            return json.dumps({"error": f"unknown tool: {name}"})
        try:
            result = self._tools[name].fn(**inputs)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

# ── 전역 레지스트리 인스턴스 ──────────────────────────────────
registry = ToolRegistry()

# ── Tool 등록 예시 (각 담당자가 자신의 tool을 여기에 추가) ────
# from backend.tools.fetch import fetch_emails
# registry.register(Tool(
#     name="fetch_emails",
#     description="Gmail에서 미읽음 이메일을 수집합니다.",
#     input_schema={
#         "type": "object",
#         "properties": {
#             "since_hours": {"type": "integer", "description": "몇 시간 전부터 (기본 24)"},
#             "max_count":   {"type": "integer", "description": "최대 수집 건수 (기본 50)"},
#         },
#     },
#     fn=fetch_emails,
# ))
```

### 4-3. ReAct 루프 (runner.py)

```python
# backend/agents/runner.py
import anthropic
from backend.agents.tool_registry import registry
from backend.agents.prompts import SYSTEM_PROMPT
from backend.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def run_agent(
    user_message: str,
    history: list[dict],
    on_step: callable = None,       # Streamlit 렌더링용 콜백
    max_iterations: int = 10,
) -> tuple[str, list[dict]]:
    """
    ReAct 루프 실행.
    반환: (최종 텍스트, 업데이트된 히스토리)
    on_step 콜백 타입:
      {"type": "thinking",    "content": str}
      {"type": "tool_call",   "name": str, "inputs": dict}
      {"type": "tool_result", "name": str, "result": str}
      {"type": "final",       "content": str}
      {"type": "error",       "content": str}
    """
    messages = history + [{"role": "user", "content": user_message}]
    tools_spec = registry.to_anthropic_spec()
    final_text = ""

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=settings.smart_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools_spec,
            messages=messages,
        )

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b.text for b in response.content if b.type == "text"]

        # 최종 답변 (tool 없음)
        if response.stop_reason == "end_turn" or not tool_calls:
            final_text = "\n".join(text_blocks)
            if on_step:
                on_step({"type": "final", "content": final_text})
            messages.append({"role": "assistant", "content": response.content})
            return final_text, messages

        # thinking 표시
        if text_blocks and on_step:
            on_step({"type": "thinking", "content": "\n".join(text_blocks)})

        messages.append({"role": "assistant", "content": response.content})

        # Tool 실행
        tool_results = []
        for tc in tool_calls:
            if on_step:
                on_step({"type": "tool_call", "name": tc.name, "inputs": tc.input})

            result_str = registry.execute(tc.name, tc.input)

            if on_step:
                on_step({"type": "tool_result", "name": tc.name, "result": result_str})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    if on_step:
        on_step({"type": "error", "content": f"max_iterations({max_iterations}) 초과"})
    return final_text, messages
```

### 4-4. 시스템 프롬프트

```python
# backend/agents/prompts.py

SYSTEM_PROMPT = """
당신은 직장인의 업무를 보조하는 AI 에이전트입니다.
사용자의 명령을 받아 제공된 tool을 자율적으로 조합해 업무를 완료합니다.

## 행동 원칙

1. 명령을 받으면 필요한 tool 순서를 먼저 판단하세요.
2. 데이터 수집 → 처리·분류 → 생성·출력 순서를 기본으로 하되, 필요에 따라 조정하세요.
3. 각 tool 결과를 확인한 후 다음 단계를 결정하세요.
4. 이미 충분한 정보가 있으면 추가 tool 호출하지 마세요.
5. 모든 tool 호출이 끝나면 사용자가 바로 이해할 수 있는 한국어 요약을 제공하세요.

## Tool 조합 패턴

| 사용자 의도 | 권장 tool 순서 |
|---|---|
| 복귀·브리핑 요청 | fetch_emails → fetch_slack → fetch_calendar → score_urgency → classify_items → write_report |
| 리포트 작성 | fetch_uploaded_file → parse_billing_data → compute_daily_stats → write_report |
| 답장 초안 | search_past_items → get_item_thread → write_draft |
| 항목 완료 처리 | update_item_status |
| 긴급 항목 파악 | fetch_emails → fetch_slack → score_urgency → filter_items |
| 일간 결산 | search_past_items(오늘) → compute_daily_stats → write_report |

## 제약사항

- 사용자 확인 없이 이메일·메시지를 자동 발송하지 마세요.
- 계약서·결재 관련 승인은 반드시 사용자에게 확인을 요청하세요.
- tool 결과가 {"error": "..."} 형태이면 다른 방법을 시도하거나 사용자에게 설명하세요.
""".strip()
```

### 4-5. LLM Provider 추상화

```python
# backend/agents/llm_client.py

import anthropic
import openai
from backend.config import settings

def complete(prompt: str, tier: str = "smart", system: str = "") -> str:
    """
    tier: "fast" | "smart"
    Provider는 LLM_PROVIDER 환경 변수로 선택.
    """
    model = settings.fast_model if tier == "fast" else settings.smart_model

    if settings.llm_provider == "anthropic":
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=model, max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    elif settings.llm_provider == "openai":
        client = openai.OpenAI(api_key=settings.openai_api_key)
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model=model, messages=msgs)
        return response.choices[0].message.content

    raise ValueError(f"unknown provider: {settings.llm_provider}")
```

| 티어 | Anthropic | OpenAI |
|---|---|---|
| Fast | claude-haiku-4-5-20251001 | gpt-4o-mini |
| Smart | claude-sonnet-4-6 | gpt-4o |

---

## 5. Tool 구현 표준

모든 tool은 아래 패턴을 따른다. tool_registry.py에 등록하면 에이전트가 자동으로 활용한다.

```python
# backend/tools/fetch.py — 예시
from backend.models import WorkItem
from backend.connectors.gmail import GmailConnector
from datetime import datetime, timedelta

def fetch_emails(since_hours: int = 24, max_count: int = 50) -> list[dict]:
    """
    반환 타입은 항상 JSON 직렬화 가능한 dict/list.
    WorkItem은 .model_dump()로 변환해서 반환.
    """
    connector = GmailConnector()
    since = datetime.now() - timedelta(hours=since_hours)
    raw_emails = connector.fetch_unread(since=since, limit=max_count)

    items = []
    for email in raw_emails:
        item = WorkItem(
            id=email["id"],
            source="gmail",
            raw_content=email["snippet"],
            summary="",             # classify 툴이 채움
            urgency_level=0,        # score 툴이 채움
            urgency_breakdown={},
            action_type="none",
            due_at=None,
            from_person=email["from"],
            status="pending",
            created_at=datetime.fromisoformat(email["date"]),
            completed_at=None,
            actual_minutes=None,
        )
        items.append(item.model_dump())
    return items
```

**Tool 등록 표준**

```python
# backend/agents/tool_registry.py 하단에 담당자별로 추가

from backend.tools.fetch import fetch_emails, fetch_slack_messages, fetch_calendar_events

registry.register(Tool(
    name="fetch_emails",
    description="Gmail에서 미읽음 이메일을 수집합니다. 부재 기간 지정 가능.",
    input_schema={
        "type": "object",
        "properties": {
            "since_hours": {"type": "integer", "description": "몇 시간 전부터 수집 (기본 24)"},
            "max_count":   {"type": "integer", "description": "최대 건수 (기본 50)"},
        },
    },
    fn=fetch_emails,
))

registry.register(Tool(
    name="score_urgency",
    description="WorkItem 목록에 긴급도 점수(1~5)를 부여합니다. T 신호 기반, LLM 미사용.",
    input_schema={
        "type": "object",
        "properties": {
            "items": {"type": "array", "description": "WorkItem dict 배열"},
        },
        "required": ["items"],
    },
    fn=score_urgency,
))

# ... 각 담당자 tool 추가
```

---

## 6. Streamlit UI (팀장 담당)

```python
# app.py — 혼합형 레이아웃: 메인(카드) + 사이드바(채팅)
import streamlit as st
from backend.agents.runner import run_agent

st.set_page_config(page_title="WhatToDo", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []
if "display_log" not in st.session_state:
    st.session_state.display_log = []

# ── 사이드바: 채팅 인터페이스 ──────────────────────────────────
with st.sidebar:
    st.title("어시스턴트")
    for entry in st.session_state.display_log:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

    if user_input := st.chat_input("업무 명령을 입력하세요"):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.display_log.append({"role": "user", "content": user_input})

        # 에이전트 실행 + 단계별 표시
        with st.chat_message("assistant"):
            step_area = st.container()
            final_placeholder = st.empty()

            def on_step(step):
                with step_area:
                    if step["type"] == "thinking":
                        with st.expander("💭 판단 중...", expanded=False):
                            st.caption(step["content"])
                    elif step["type"] == "tool_call":
                        with st.expander(f"🔧 `{step['name']}` 실행", expanded=True):
                            st.json(step["inputs"])
                    elif step["type"] == "tool_result":
                        with st.expander(f"✅ `{step['name']}` 완료", expanded=False):
                            st.code(step["result"][:300], language="json")
                    elif step["type"] == "final":
                        final_placeholder.markdown(step["content"])
                    elif step["type"] == "error":
                        st.error(step["content"])

            final_text, updated_history = run_agent(
                user_message=user_input,
                history=st.session_state.history,
                on_step=on_step,
            )
            st.session_state.history = updated_history
            st.session_state.display_log.append({"role": "assistant", "content": final_text})

# ── 메인: 브리핑 카드 ──────────────────────────────────────────
st.title("WhatToDo")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔄 브리핑 시작", use_container_width=True):
        final_text, updated_history = run_agent(
            user_message="복귀 브리핑 실행해줘",
            history=st.session_state.history,
        )
        st.session_state.history = updated_history
        st.rerun()

if briefing := st.session_state.get("briefing"):
    col1, col2, col3 = st.columns(3)
    col1.metric("긴급 항목", briefing["stats"]["urgent"])
    col2.metric("오늘 처리", briefing["stats"].get("today", 0))
    col3.metric("예상 시간", f"{briefing['stats']['estimated_minutes']}분")

    for card in briefing.get("sections", {}).get("immediate", []):
        with st.container(border=True):
            st.markdown(f"🔴 **{card['summary']}**")
            st.caption(f"{card['from_person']} · {card['estimated_minutes']}분")
            if st.checkbox("완료", key=f"done_{card['id']}"):
                run_agent(
                    f"{card['id']} 완료 처리해줘",
                    history=st.session_state.history,
                )
                st.rerun()
```

---

## 7. Urgency Engine (scoring 툴)

### MVP — T 신호 단독

```python
# backend/tools/scoring.py
from math import exp, ceil
from datetime import datetime

def time_score(due_at: datetime | None, received_at: datetime, now: datetime) -> float:
    if due_at:
        hours_left = (due_at - now).total_seconds() / 3600
        if hours_left <= 0:
            return 1.0
        return 1 - exp(-3 / max(hours_left, 0.5))
    else:
        hours_elapsed = (now - received_at).total_seconds() / 3600
        return min(hours_elapsed / 72, 0.6)

def score_urgency(items: list[dict]) -> list[dict]:
    now = datetime.now()
    for item in items:
        due_at = datetime.fromisoformat(item["due_at"]) if item.get("due_at") else None
        received_at = datetime.fromisoformat(item["created_at"])
        t = time_score(due_at, received_at, now)
        item["urgency_level"] = ceil(t * 5)
        item["urgency_breakdown"] = {"T": round(t, 3)}
    return items
```

### 확장 — 5-신호 가중합 (온보딩 프로필·이력 축적 후 전환)

```python
urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S
urgency_level = ceil(urgency_score * 5)
```

| 신호 | 가중치 | 측정 방법 |
|---|---|---|
| T (마감 잔여 시간) | 0.35 | 지수 감쇠. 초과=1.0, 24h 후=0.12 |
| A (발신자 중요도) | 0.25 | 온보딩 user_profile → 서명 파싱 → 행동 추정 → 기본값 0.4 |
| F (반복 추적) | 0.20 | 미응답 동일 발신자 수, log 스케일 |
| K (키워드) | 0.10 | "urgent"=+0.9, "FYI"=−0.4 |
| S (소스·채널) | 0.10 | Slack DM=0.85, Jira blocker=0.90, 이메일 CC=0.35 |

---

## 8. TinyDB 데이터 저장

```python
# backend/db/store.py
from tinydb import TinyDB, Query
from pathlib import Path

DB_DIR = Path("backend/db/data")

def get_table(name: str):
    db = TinyDB(DB_DIR / f"{name}.json")
    return db.table(name)

# 사용 예시
items_table = get_table("work_items")
Item = Query()

# 저장
items_table.insert(work_item.model_dump())

# 조회
pending = items_table.search(Item.status == "pending")

# 업데이트
items_table.update({"status": "done"}, Item.id == item_id)
```

| 파일 | 테이블 | 주요 필드 |
|---|---|---|
| `work_items.json` | work_items | id, source, summary, urgency_level, action_type, status, due_at, completed_at |
| `briefings.json` | briefings | id, absence_days, stats, sections, summary_text |
| `daily_summaries.json` | daily_summaries | id, date, stats, narrative |
| `kpi_reports.json` | kpi_reports | id, period, aggregated, narrative |
| `user_profile.json` | user_profile | key_people, key_projects, company_context |

---

## 9. Phase 2 — Orchestrator + SubAgents 전환

Phase 1 tool 코드를 재사용하면서 레이어만 추가한다.

```python
# backend/agents/orchestrator.py (Phase 2 신규)

ORCHESTRATOR_TOOLS = [
    {
        "name": "call_briefing_agent",
        "description": "이메일·슬랙·캘린더 수집 및 우선순위 브리핑 생성",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}}},
    },
    {
        "name": "call_report_agent",
        "description": "데이터 파싱 및 각종 리포트 작성",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}}},
    },
    {
        "name": "call_action_agent",
        "description": "항목 완료 처리, 답장 초안, 상태 변경",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}}},
    },
    {
        "name": "call_search_agent",
        "description": "과거 항목 조회, 사내 문서 RAG 검색",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}}},
    },
]

# SubAgent 맵 — Phase 1 tool을 각 SubAgent가 소유
SUBAGENT_MAP = {
    "call_briefing_agent": run_briefing_agent,  # fetch + score + classify + write_report
    "call_report_agent":   run_report_agent,    # parse_billing + compute + write_report
    "call_action_agent":   run_action_agent,    # update_status + write_draft
    "call_search_agent":   run_search_agent,    # search_items + search_docs(RAG)
}
```

**팀 분업 (Phase 2)**

| 담당 | SubAgent |
|---|---|
| 팀장 | Orchestrator 구현, Streamlit 유지 |
| #2 | BriefingAgent (fetch tool 소유) |
| #3 | BriefingAgent 내 score/classify 담당 |
| #4 | ReportAgent (write tool 소유) |
| #5 | ActionAgent (action/search tool 소유) |
| #6 | SearchAgent + RAG (ChromaDB) |

---

## 10. FastAPI 엔드포인트

### MVP — OAuth 콜백만

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/auth/gmail/callback` | Gmail OAuth 리디렉션 수신 |
| GET | `/auth/slack/callback` | Slack OAuth 리디렉션 수신 |
| GET | `/health` | 서버 상태 확인 |

### Phase 2 — REST API 추가 (브라우저 확장 전환 시)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/agent/run` | 에이전트 명령 실행 |
| GET | `/briefing/{id}` | 브리핑 결과 조회 |
| PATCH | `/items/{id}` | 항목 상태 변경 |
| GET | `/summary/daily` | 일간 결산 조회 |
| GET | `/summary/weekly` | 주간 KPI 조회 |

---

## 11. 패키지 목록

```toml
# pyproject.toml
[project]
name = "whattodo"
requires-python = ">=3.11"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "streamlit",
    "tinydb",
    "apscheduler",
    "anthropic",
    "openai",
    "httpx",
    "authlib",
    "pydantic-settings",
]

[dependency-groups]
dev = ["pytest", "pytest-asyncio", "httpx"]
```

```bash
# 실행
uv run uvicorn backend.main:app --reload   # FastAPI (OAuth 콜백)
uv run streamlit run app.py                # Streamlit UI
```

---

## 12. 환경 변수

```bash
# .env

# LLM
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# 모델 티어 (Provider 교체 시 이 두 줄만 수정)
FAST_MODEL=claude-haiku-4-5-20251001
SMART_MODEL=claude-sonnet-4-6

# OAuth
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
GOOGLE_CALENDAR_CLIENT_ID=
GOOGLE_CALENDAR_CLIENT_SECRET=
JIRA_API_TOKEN=
JIRA_BASE_URL=

# 앱
SECRET_KEY=
STREAMLIT_PORT=8501

# 파이프라인
COLLECTION_LIMIT_PER_SOURCE=200
BRIEFING_TIMEOUT_SECONDS=60
AGENT_MAX_ITERATIONS=10

# Urgency 가중치 (확장 단계에서 활성화)
URGENCY_WEIGHT_TIME=0.35
URGENCY_WEIGHT_AUTHORITY=0.25
URGENCY_WEIGHT_FOLLOWUP=0.20
URGENCY_WEIGHT_KEYWORD=0.10
URGENCY_WEIGHT_SOURCE=0.10
```

---

## 13. 주요 설계 결정 (ADR)

| 결정 | 선택 | 이유 |
|---|---|---|
| Phase 1 에이전트 구조 | 단일 WorkAssistantAgent + TOOL_REGISTRY | 팀 진입 장벽 최소화. tool 추가만으로 기능 확장 가능. |
| Phase 2 전환 방식 | Phase 1 tool 재사용 + Orchestrator 레이어 추가 | 코드 재작성 없음. SubAgent에 tool 재배치만. |
| UI 방식 | Streamlit 고정 (혼합형 레이아웃) | 팀 전체가 Python만으로 기여 가능. |
| DB | TinyDB (MVP) → PostgreSQL (Phase 2+) | 서버 불필요. 스키마 동일하게 유지해 마이그레이션 용이. |
| LLM Provider | 추상화 래퍼 (Fast / Smart 티어) | llm_client.py 1개 파일만 수정하면 Provider 교체. |
| Tool 추가 방식 | 기능 제안 → 업무 분해 → tool 구현 → registry 등록 | 에이전트 로직 불변. 병렬 개발 가능. |
| 자동 발송 | 가드레일로 전면 차단 | 사용자 확인 필수. 계약·결재 관련 자동 승인 불가. |
