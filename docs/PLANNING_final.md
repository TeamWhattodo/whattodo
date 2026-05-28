# WhatToDo — 직장인 업무 보조 에이전트 기획서

## 1. 서비스 개요

**WhatToDo**는 직장인의 반복 업무(이메일 확인, 리포트 작성, 항목 처리, 일정 관리 등)를 AI 에이전트가 자율적으로 수행하는 **범용 업무 보조 서비스**다.

사용자가 자연어로 명령하면 에이전트가 필요한 tool을 스스로 선택·조합해 업무를 완료한다.

| 항목 | 내용 |
|---|---|
| 서비스명 | WhatToDo |
| 타깃 사용자 | 이메일·슬랙·Jira 등 여러 도구를 동시에 사용하는 직장인 |
| 핵심 가치 | 명령 하나로 업무가 완료된다 |
| 서비스 형태 | Streamlit 챗 + 카드 UI (전 Phase 고정) |

### 핵심 기능

| 기능 | 설명 | Phase |
|---|---|---|
| 복귀 브리핑 | 부재 기간 쌓인 항목 수집·분류·우선순위 카드 | 1 |
| 자연어 명령 처리 | "정산 리포트 작성해줘" 등 범용 업무 실행 | 1 |
| 답장 초안 생성 | 이메일·슬랙 답장 초안 자동 작성 | 1 |
| 항목 상태 관리 | 완료·스누즈·이월 처리 | 1 |
| 일간 결산 | 완료 항목·이월 항목·처리 통계 자동 집계 | 2 |
| 주간 KPI 리포트 | 완료율·응답 시간·채널별 부하 등 생산성 지표 | 2 |
| 사내 규정 엔진 | 회사별 보고 체계·승인 규정을 에이전트 동작에 반영 | 2 |
| 멀티 에이전트 전환 | Orchestrator + SubAgents 구조로 확장 | 2 |

---

## 2. 아키텍처

### 역할 분리 원칙

```
Orchestrator  → "누가 할 건지" 결정 (intent 분류 + 라우팅)
SubAgent      → "어떻게 할 건지" 자율 결정 (도메인 내 tool_use 루프)
Tool          → "실제로 한 가지 일" 실행 (순수 함수)
```

- **Orchestrator**: LLM Smart 티어. intent만 판단하고 SubAgent에 위임. tool 순서에 관여하지 않는다.
- **SubAgent**: LLM Fast 티어. 도메인 내 tool을 자율 선택·조합. 순서는 LLM이 결정하되, 제약(constraint)만 시스템 프롬프트로 명시한다.
- **Tool**: LLM 없음 또는 Fast 티어. 단일 책임. Phase 1 TOOL_REGISTRY 코드를 그대로 재사용한다.

### Phase 1 — 단일 에이전트 + Tool Registry (완료)

단일 `WorkAssistantAgent`가 TOOL_REGISTRY에 등록된 tool을 자율 선택·조합해 모든 요청을 처리한다.

```
사용자 명령
    │
    ▼
[WorkAssistantAgent]  ← LLM Smart, tool_use 루프 (max 10)
    │
    ├─► fetch_messages      (Gmail / Slack / Calendar 수집)
    ├─► score_urgency       (긴급도 계산, LLM 없음)
    ├─► classify_items      (액션 타입 + 요약, LLM Fast)
    ├─► write_report        (리포트·브리핑 생성, LLM Smart)
    ├─► write_draft         (답장 초안 생성, LLM Smart)
    ├─► update_item_status  (완료·스누즈, LLM 없음)
    ├─► search_items        (과거 항목 조회, LLM 없음)
    └─► compute_stats       (통계 집계, LLM 없음)
    │
    ▼
Streamlit UI (카드 + 채팅 사이드바)
```

**Tool 추가 원칙**: 팀원이 기능을 제안하면 업무를 tool 단위로 분해해 TOOL_REGISTRY에 등록한다. 에이전트 로직은 건드리지 않는다.

### Phase 2 — Orchestrator + SubAgents (LangGraph)

tool이 누적되고 업무 유형이 다양해지면 Orchestrator가 요청을 전문 SubAgent에게 위임하는 구조로 전환한다.

```
사용자 명령
    │
    ▼
[LangGraph State]
WhatToDoState {
    user_input, intent, work_items,
    results, error, user_preferences,
    retry_count, has_write_output
}
    │
    ▼
[Orchestrator]  ← LLM Smart, intent 분류 전담
    │
    ├─► [BriefingAgent]   도메인: fetch · score · classify · write
    ├─► [ReportAgent]     도메인: parse · compute · write
    ├─► [ActionAgent]     도메인: search · draft · update
    └─► [SearchAgent]     도메인: search_items · RAG
    │
    ▼
[collect_results] → State 업데이트
    │
    ▼
[output_validator]  ← write_* 출력만 · LLM Fast · 최대 2회 재시도
    │                  is_sufficient=false → SubAgent 재호출
    ▼
Streamlit UI (변경 없음)

**복합 의도 병렬 처리 — Send API**
```python
from langgraph.types import Send

def route_by_intent(state):
    intents = state["intent"].split(",")  # "report,search" → 병렬
    if len(intents) > 1:
        return [Send(i.strip(), state) for i in intents]
    return intents[0]
```
```

**구조 패러다임 — Hierarchical Multi-Agent**

```
Flat (Phase 1)                Hierarchical (Phase 2)
──────────────────            ──────────────────────────
Agent 1개                     Orchestrator (LLM Smart)
  ├─ tool A                       ├─ BriefingAgent (LLM Fast)
  ├─ tool B                       │     ├─ tool A · B · C
  └─ tool C                       └─ ReportAgent (LLM Fast)
                                        └─ tool D · E · F
```

tool이 누적될수록 Flat 구조는 LLM의 tool 선택 정확도가 저하된다. Hierarchical은 Orchestrator가 intent만 판단하고, 각 SubAgent는 4~8개 tool만 보므로 집중도가 유지된다.

**LangGraph 노드 전체 목록**

| 노드 | 타입 | 역할 |
|---|---|---|
| `intent_classifier` | LLM Smart | intent 분류 + 복합 의도 보정 |
| `briefing` | LLM Fast | fetch · score · classify · write |
| `report` | LLM Fast | parse · compute · write |
| `action` | LLM Fast | search · draft · update |
| `search` | LLM Fast | RAG · 과거 항목 조회 |
| `chat` | LLM Fast | 일반 대화 |
| `collect` | 코드 | SubAgent 결과 병합 |
| `output_validator` | LLM Fast | write_* 출력 품질 검증 · 최대 2회 재시도 |

**agentic 설계 원칙**: SubAgent는 도메인 내에서 tool 순서를 LLM이 자율 결정한다. 시스템 프롬프트는 순서(sequence)가 아닌 제약(constraint)만 명시한다.

```python
# 올바른 방향 — 제약만 명시, 순서는 LLM 자율
BRIEFING_AGENT_SYSTEM = """
당신은 브리핑 전담 에이전트입니다.
사용 가능한 tool: fetch_emails, fetch_slack_messages, fetch_calendar_events,
                  score_urgency, classify_items, write_report

제약:
- score_urgency는 반드시 fetch 완료 후 실행
- write_report는 반드시 classify 완료 후 실행
- 수집 결과가 0건이면 score/classify 생략 가능

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.
"""
```

**전환 조건**: tool이 15개 이상 누적되거나, 단일 에이전트의 tool 선택 정확도가 저하될 때 전환한다. Phase 1 tool 코드는 SubAgent에 재배치만 하면 된다.

---

## 3. 커버 가능한 업무 및 Tool 분해

### Tool 구현 상태

| 상태 | 수량 | 목록 |
|---|---|---|
| ✅ 완료 (Phase 1) | 15개 | fetch_emails · fetch_slack · fetch_calendar · score_urgency · classify_items · write_report · write_draft · fetch_uploaded_file · parse_billing_data · compute_daily_stats · compute_kpi · update_item_status · search_past_items · get_item_thread · search_company_docs |
| 🔶 Phase 2 구현 필요 | 4개 | fetch_jira_issues · fetch_notion_pages · parse_receipt · create_calendar_block |

### 업무 도메인과 Tool 목록

#### 도메인 A — 수집 (Fetch)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `fetch_emails` | since_hours, max_count | `WorkItem[]` | ❌ |
| `fetch_slack_messages` | since_hours, mention_only | `WorkItem[]` | ❌ |
| `fetch_calendar_events` | date_range | `WorkItem[]` | ❌ |
| `fetch_jira_issues` | assignee, due_within_days | `WorkItem[]` | ❌ |
| `fetch_uploaded_file` | file_path, file_type | `ParsedFile` | ❌ |

#### 도메인 B — 분류 (Classify)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `score_urgency` | `WorkItem[]` | `ScoredItem[]` | ❌ |
| `classify_items` | `WorkItem[]` | `ClassifiedItem[]` | ✅ Fast |
| `group_by_topic` | `WorkItem[]` | `TopicGroup[]` | ✅ Fast |
| `filter_items` | `WorkItem[]`, condition | `WorkItem[]` | ❌ |

#### 도메인 C — 작성 (Write)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `write_report` | report_type, data | `ReportDraft` | ✅ Smart |
| `write_draft` | item_id, tone | `DraftText` | ✅ Smart |
| `write_meeting_agenda` | topic, context | `AgendaText` | ✅ Smart |

#### 도메인 D — 액션 (Action)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `update_item_status` | item_id, status | `UpdateResult` | ❌ |
| `create_calendar_block` | title, start, end | `CalendarEvent` | ❌ |
| `update_jira_issue` | issue_key, status | `UpdateResult` | ❌ |

#### 도메인 E — 조회 (Search)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `search_past_items` | query, date_range | `WorkItem[]` | ❌ |
| `search_company_docs` | query | `DocChunk[]` | ❌ (RAG) |
| `get_item_thread` | item_id, source | `ThreadItems[]` | ❌ |

> **`search_company_docs` 구현 노트 (RAG)**
> - 현재 지원 형식: PDF (`PyPDFLoader`)
> - 추후 확장: Word (`Docx2txtLoader`), Markdown, HTML
> - 벡터 DB: ChromaDB (로컬) / `backend/db/data/policy_store/`
> - 임베딩: `jhgan/ko-sroberta-multitask` (한국어 특화, 무료)
> - 문서 수집: `backend/scripts/ingest_policy.py`

#### 도메인 F — 분석 (Compute)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `compute_daily_stats` | date | `DailyStats` | ❌ |
| `compute_kpi` | period | `KPIAggregated` | ❌ |
| `parse_billing_data` | file_path, month | `BillingData` | ❌ |
| `parse_receipt` | image_path | `ReceiptItem[]` | ❌ |

#### 도메인 G — SubAgent 위임 (Phase 2)

Orchestrator가 SubAgent를 tool처럼 호출한다.

| Tool | 위임 대상 | 도메인 |
|---|---|---|
| `call_briefing_agent` | BriefingAgent | A·B·C |
| `call_report_agent` | ReportAgent | C·F |
| `call_action_agent` | ActionAgent | D·E |
| `call_search_agent` | SearchAgent | E (RAG 포함) |

### SubAgent별 도메인 tool 목록

```
BriefingAgent (Fast 티어)
  fetch_emails · fetch_slack_messages · fetch_calendar_events · Jira MCP 툴
  score_urgency · classify_items · write_report

ReportAgent (Fast 티어)
  fetch_uploaded_file · parse_billing_data · parse_receipt
  compute_daily_stats · compute_kpi · write_report

ActionAgent (Fast 티어)
  search_past_items · get_item_thread
  write_draft · update_item_status · create_calendar_block

SearchAgent (Fast 티어)
  search_past_items · search_company_docs · get_item_thread
```

### 업무 → SubAgent 라우팅 패턴

Orchestrator 시스템 프롬프트에 포함해 라우팅 정확도를 높인다.

| 업무 | 라우팅 | 비고 |
|---|---|---|
| 복귀 브리핑 | BriefingAgent | 내부 tool 순서는 자율 |
| 정산 리포트 | ReportAgent | 파일 업로드 포함 시 |
| 답장 초안 | ActionAgent | 스레드 맥락 수집 포함 |
| 주간 결산 | ReportAgent | compute_kpi 포함 |
| 미팅 준비 | BriefingAgent + SearchAgent | 복합 의도 시 병렬 위임 가능 |
| 긴급 항목 파악 | BriefingAgent | urgency 필터 판단은 자율 |
| 사규 조회 | SearchAgent | RAG 단독 |
| 규정 기반 정산 검증 | ReportAgent + SearchAgent | 복합 의도 |

---

## 4. 사용자 시나리오

### 시나리오 A — 월요일 아침 복귀 브리핑

```
사용자: "주말 동안 쌓인 것 정리해줘"

Orchestrator → intent: "briefing" → BriefingAgent 위임

BriefingAgent (tool 순서 자율 결정):
  → fetch_emails(since_hours=60)
  → fetch_slack_messages(since=60h)
  → fetch_calendar_events(3일치)
  → fetch_jira_issues(due_within_days=7)
  → score_urgency(전체 235건)
  → classify_items(urgency≥3 항목)
  → write_report(briefing)

결과: 브리핑 카드 표시
  🔴 지금 당장 (3건) — 계약서 서명, 배포 승인, 예산 승인
  🟡 오늘 안에 (7건) — 주간 회의 준비, 디자인 피드백 등
  ⚪ FYI (180건) — 접혀 있음
```

### 시나리오 B — 정산 리포트 작성

```
사용자: "5월 정산 리포트 작성해줘" (파일 업로드 포함)

Orchestrator → intent: "report" → ReportAgent 위임

ReportAgent (tool 순서 자율 결정):
  → fetch_uploaded_file(billing_may.csv)
  → parse_billing_data(month=2026-05)
  → compute_daily_stats(기간)
  → write_report(billing)

결과: 리포트 초안 → 다운로드 버튼
```

### 시나리오 C — 자연어 항목 처리

```
사용자: "박팀장 DM 답장 초안 써줘"

Orchestrator → intent: "action" → ActionAgent 위임

ActionAgent (tool 순서 자율 결정):
  → search_past_items(query="박팀장 DM", source=slack)
  → get_item_thread(item_id=...)
  → write_draft(tone=formal)

결과: 초안 표시 → 사용자 확인 후 복사
```

### 시나리오 D — 이월 항목 캘린더 블록 생성

```
사용자: "이월된 것 내일 오전으로 잡아줘"

Orchestrator → intent: "action" → ActionAgent 위임

ActionAgent:
  → search_past_items(status=snoozed)
  → create_calendar_block(title=..., start=내일_09:00)

결과: 캘린더 블록 생성 완료 알림
```

### 시나리오 E — 사내 규정 조회 및 영수증 검증

```
사용자: "이 영수증 규정에 맞아?" (영수증 이미지 업로드)

Orchestrator → intent: "search" → SearchAgent 위임
             → (파일 있음) → ReportAgent에도 병렬 위임

ReportAgent:
  → parse_receipt(image_path="receipt.jpg") [식대 32,000원]

SearchAgent:
  → search_company_docs(query="식대 규정 한도")

Orchestrator 취합:
결과: "식대 32,000원 / 규정 한도 30,000원 → 2,000원 초과"
```

### 시나리오 F — 퇴근 전 일간 결산 (스케줄)

```
APScheduler 18:00 → run_agent("일간 결산 실행")

Orchestrator → intent: "report" → ReportAgent 위임

ReportAgent:
  → search_past_items(오늘, status=done)
  → search_past_items(오늘, status=pending)
  → compute_daily_stats(오늘)
  → write_report(daily_summary)

결과:
  ✅ 완료 7건 / 실제 48분
  ⏭ 이월 3건 → 내일 캘린더 블록 제안
```

---

## 5. 온보딩

온보딩은 최초 1회 실행된다. **MCP 커넥터 연결**과 **사내 문서 RAG ingest** 두 흐름이 병렬로 진행되며, 둘 다 완료되어야 런타임이 활성화된다.

### MCP 커넥터 연결

| 단계 | 내용 |
|---|---|
| 서비스 선택 | Gmail · Slack · Jira · Notion (추후: Calendar · Linear) |
| OAuth 인증 | 각 서비스 authorization URL 리다이렉트 → 권한 승인 |
| 토큰 수신 | access_token · refresh_token 발급 |
| 암호화 저장 | AES-256 · `connectors/auth.py` · 만료 시 자동 갱신 |
| 연결 확인 | `since_hours=1` 테스트 수집으로 검증 |

### 사내 문서 RAG ingest

| 단계 | 내용 |
|---|---|
| 문서 업로드 | PDF (현재) · DOCX · MD (추후) · 복수 업로드 가능 |
| 문서 로더 | `PyPDFLoader` (추후 `Docx2txtLoader` · `UnstructuredMarkdownLoader`) |
| 청크 분할 | `RecursiveCharacterTextSplitter` · chunk_size=500 · overlap=50 |
| 임베딩 생성 | `jhgan/ko-sroberta-multitask` (한국어 특화, 무료) |
| ChromaDB 저장 | `backend/db/data/policy_store/` · 신규 문서 추가 시 재실행 |

`search_company_docs(query, top_k=3)` — 런타임에서 SearchAgent·ReportAgent가 호출. ChromaDB 비어 있으면 안내 문구 반환.

### 온보딩 완료 조건

```
필수: MCP 커넥터 1개 이상 연결
선택: 사내 문서 업로드 (없으면 search_company_docs 비활성)
Phase 3: 직군 선택 → DomainAgent 활성화
  영업(SalesAgent) · 개발(DevAgent) · 재무(FinanceAgent)
  인사(HRAgent) · 마케팅(MarketingAgent)
→ 완료 시 런타임 활성화
```

### 파일 구조

```
backend/
  connectors/
    auth.py          ← OAuth 토큰 관리 (AES-256)
    gmail.py · slack.py · jira.py · notion.py
  tools/
    policy_search.py ← search_company_docs tool
  db/data/
    policy_store/    ← ChromaDB 벡터 DB (자동 생성)
  scripts/
    ingest_policy.py ← 온보딩 ingest 실행 스크립트
```

---

## 6. 기술 아키텍처

### Phase 1 (완료)

```
┌─────────────────────────────────────┐
│         Streamlit (단일 앱)          │
└──────────────┬──────────────────────┘
               │ Python 직접 import
┌──────────────▼──────────────────────┐
│        WorkAssistantAgent            │
│   LLM Smart + TOOL_REGISTRY          │
│   tool_use 루프 (max 10 iter)        │
└──────┬──────────────────────────────┘
       │
┌──────▼──────────────────────────────┐
│           TOOL_REGISTRY              │
│  fetch / score / classify / write    │
│  update / search / compute           │
└──────┬──────────────────────────────┘
       │
┌──────▼──────────────────────────────┐
│           Data Layer                 │
│  TinyDB (JSON) · heapq (Queue)      │
└─────────────────────────────────────┘
```

### Phase 2 (LangGraph)

```
┌─────────────────────────────────────┐
│         Streamlit (변경 없음)        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         LangGraph Graph              │
│                                      │
│  ┌─────────────────────────────┐    │
│  │  WhatToDoState               │    │
│  │  user_input · intent         │    │
│  │  work_items · results        │    │
│  │  error · user_preferences    │    │
│  └─────────────────────────────┘    │
│                                      │
│  [intent_classifier]  ← LLM Smart   │
│         │                            │
│  conditional_edges + Send API        │
│    briefing → [BriefingAgent]        │
│    report   → [ReportAgent]          │
│    action   → [ActionAgent]          │
│    search   → [SearchAgent]          │
│    chat     → [general_chat]         │
│    복합의도 → Send API 병렬 실행      │
│         │                            │
│  [collect_results]                   │
│         │                            │
│  [output_validator]  ← LLM Fast     │
│    write_* 출력만 검증               │
│    is_sufficient=false → 재시도(max 2)│
└──────────────┬──────────────────────┘

### 검증 3단계 (Harnessing)

```python
# ① intent 보정 — rule-based, 비용 0
# 복합 의도 누락 보정
def validate_intent(intent: str, user_input: str) -> str:
    keywords = {
        "briefing": ["정리", "브리핑", "쌓인", "복귀"],
        "report":   ["리포트", "정산", "결산", "KPI"],
        "action":   ["초안", "답장", "완료", "처리"],
        "search":   ["규정", "한도", "찾아", "검색"],
    }
    matched = [k for k, words in keywords.items()
               if any(w in user_input for w in words)]
    if len(matched) > 1 and "," not in intent:
        return ",".join(matched)
    return intent

# ② constraint check — rule-based, 비용 0
# tool 실행 전 선후관계 검증
CONSTRAINTS = {
    "score_urgency":  {"requires": ["fetch_emails","fetch_slack_messages","fetch_calendar_events"]},
    "classify_items": {"requires": ["score_urgency"]},
    "write_report":   {"requires": ["classify_items"]},
    "write_draft":    {"requires": ["get_item_thread"]},
}

# ③ output_validator — LLM Fast, write_* 출력만 적용
VERIFY_PROMPT = """
다음 기준으로 출력을 평가하세요.
1. 사용자 요청에 직접 답했는가
2. 누락된 핵심 정보가 없는가
3. 사실 오류나 모순이 없는가
JSON: {"is_sufficient": bool, "feedback": "미흡 시만 기재"}
"""
```
               │
┌──────────────▼──────────────────────┐
│       기존 TOOL_REGISTRY 재사용      │
│  (Phase 1 tool 코드 변경 없음)       │
└─────────────────────────────────────┘

APScheduler (LangGraph 외부)
  18:00 → run_agent("일간 결산 실행")
  금 17:00 → run_agent("주간 KPI 리포트 생성")
```

### LangGraph 노드 구현 패턴

```python
# backend/agents/graph.py

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal

class WhatToDoState(TypedDict):
    user_input: str
    intent: Literal["briefing", "report", "action", "search", "chat"]
    work_items: list
    results: dict
    error: str | None
    user_preferences: dict   # memory 레이어 (Phase 3)

def intent_classifier(state: WhatToDoState) -> WhatToDoState:
    """LLM Smart — intent 분류만 담당. tool 순서에 관여하지 않는다."""
    ...

def route_by_intent(state: WhatToDoState) -> str:
    return state["intent"]

graph = StateGraph(WhatToDoState)
graph.add_node("classify_intent", intent_classifier)
graph.add_node("briefing",  briefing_agent_node)
graph.add_node("report",    report_agent_node)
graph.add_node("action",    action_agent_node)
graph.add_node("search",    search_agent_node)
graph.add_node("chat",      general_chat_node)
graph.add_node("collect",   collect_results)

graph.add_edge(START, "classify_intent")
graph.add_conditional_edges("classify_intent", route_by_intent, {
    "briefing": "briefing",
    "report":   "report",
    "action":   "action",
    "search":   "search",
    "chat":     "chat",
})
for node in ["briefing", "report", "action", "search", "chat"]:
    graph.add_edge(node, "collect")
graph.add_edge("collect", END)
```

### SubAgent 구현 패턴

```python
# backend/agents/subagents/briefing_agent.py

BRIEFING_AGENT_TOOLS = [
    "fetch_emails", "fetch_slack_messages", "fetch_calendar_events",
    "score_urgency", "classify_items", "write_report",
]

BRIEFING_AGENT_SYSTEM = """
당신은 브리핑 전담 에이전트입니다.
사용 가능한 tool: fetch_emails, fetch_slack_messages, fetch_calendar_events,
                  score_urgency, classify_items, write_report

제약:
- score_urgency는 반드시 fetch 완료 후 실행
- write_report는 반드시 classify 완료 후 실행
- 수집 결과가 0건이면 score/classify 생략 가능

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.
"""
# 순서(sequence)가 아닌 제약(constraint)만 명시 — agentic 설계 원칙

def briefing_agent_node(state: WhatToDoState) -> WhatToDoState:
    subset_registry = build_subset_registry(BRIEFING_AGENT_TOOLS)
    result, _ = run_agent(
        user_message=state["user_input"],
        system=BRIEFING_AGENT_SYSTEM,
        model=settings.fast_model,
        registry=subset_registry,
    )
    return {**state, "results": {**state["results"], "briefing": result}}
```

---

## 7. 데이터 모델

```python
# backend/models.py

class WorkItem(BaseModel):
    id: str
    source: Literal["gmail", "slack", "calendar", "jira", "notion"]
    raw_content: str
    summary: str
    urgency_level: int
    urgency_breakdown: dict
    action_type: Literal["reply", "approve", "review", "fyi", "none"]
    due_at: datetime | None
    from_person: str | None
    status: Literal["pending", "done", "snoozed"]
    created_at: datetime
    completed_at: datetime | None
    actual_minutes: int | None

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

class BriefingResult(BaseModel):
    briefing_id: str
    absence_days: int
    stats: dict
    sections: dict
    contacts_needed: list[dict]
    summary_text: str

class WhatToDoState(BaseModel):   # LangGraph State (Phase 2)
    user_input: str
    intent: str
    work_items: list[WorkItem]
    results: dict
    error: str | None
    retry_count: int              # output_validator 재시도 횟수 (max 2)
    has_write_output: bool        # write_* tool 호출 여부 → validator 진입 조건
    user_preferences: dict        # Phase 3: memory 레이어
```

---

## 8. 개인정보 및 보안

- 이메일·메시지 원문은 처리 후 즉시 삭제, 요약본만 저장
- OAuth 토큰 암호화 저장 (AES-256)
- AI 처리는 Anthropic API (학습 미사용)
- 모든 발송 액션은 사용자 확인 필수 (가드레일)
- Phase 3: `interrupt()` 노드로 발송 전 승인 단계 추가

---

## 9. 수익 모델

| 플랜 | 대상 | 가격 | 포함 내용 |
|---|---|---|---|
| Free | 개인 | 무료 | 소스 2개, 월 명령 30회 |
| Pro | 개인 | $9/월 | 소스 무제한, 명령 무제한, 파일 업로드 |
| Team | 팀 | $6/인/월 | Pro + 팀 대시보드, 관리자 리포트 |
| Enterprise | 기업 | 협의 | 온프레미스, SSO, 감사 로그 |

---

## 10. 개발 로드맵

### Phase 1 — 단일 에이전트 MVP (완료)

| 포함 | 제외 (Phase 2) |
|---|---|
| WorkAssistantAgent + TOOL_REGISTRY | Orchestrator + SubAgents |
| 도메인 A·B·C 핵심 tool (8개) | 도메인 E·F 고급 tool |
| Gmail + Slack + Calendar 커넥터 | Jira / Notion 커넥터 |
| Streamlit 혼합형 UI | 슬랙 봇 인터페이스 |
| Urgency Engine (T 신호) | 5-신호 가중합 |
| TinyDB 저장 | PostgreSQL 마이그레이션 |
| OAuth 인증 (Gmail, Slack) | Policy Engine |

### Phase 2 — Orchestrator + SubAgents (6주)

#### 구현 우선순위

| 순서 | 항목 | 담당 |
|---|---|---|
| 1 | LangGraph State + Graph 뼈대 | 팀장 |
| 2 | intent_classifier 노드 (Orchestrator) | 팀장 |
| 3 | BriefingAgent 노드 (Phase 1 코드 재배치) | #2·#3 |
| 4 | ReportAgent 노드 | #4·#6 |
| 5 | ActionAgent 노드 | #5 |
| 6 | SearchAgent + RAG | #6 |
| 7 | APScheduler 연동 (일간·주간) | #6 |
| 8 | parse_receipt tool 추가 | #4 |
| 9 | create_calendar_block 완성 | #5 |

#### 추가되는 기능

- [ ] LangGraph Orchestrator + 4개 SubAgent
- [ ] Jira / Notion 커넥터
- [ ] 일간 결산 자동화 (18:00 스케줄)
- [ ] 주간 KPI 리포트 자동 생성 (금 17:00 스케줄)
- [ ] Policy Engine — 사내 규정 RAG (`search_company_docs`)
- [ ] `parse_receipt` tool (영수증 이미지 → 규정 대조)
- [ ] `create_calendar_block` 완성 (이월 항목 → 캘린더 제안)
- [ ] 슬랙 봇 인터페이스

#### 브랜치 전략

```
main ← 배포 가능 상태만. 주 1회 (금요일) dev → main
  └ dev
      ├ feat/langgraph-core       (팀장)
      ├ feat/briefing-agent       (#2·#3)
      ├ feat/report-agent         (#4·#6)
      ├ feat/action-agent         (#5)
      ├ feat/search-agent-rag     (#6)
      └ feat/scheduler            (#6)
```

### Phase 3 — 개인화 + 팀 기능 + 직군 확장 (6주)

- [ ] Human-in-the-loop: LangGraph `interrupt()` — 발송 전 사용자 승인
- [ ] Memory 레이어: `user_preferences` State 필드 → 선호 누적
- [ ] 멀티턴 태스크: LangGraph `checkpointer` — 며칠에 걸친 태스크 지속
- [ ] Proactive 알림: urgency 5 감지 시 사용자 요청 없이 먼저 알림
- [ ] **DomainAgent 확장** — 온보딩 직군 선택 시 활성화
  - SalesAgent: CRM 연동 · 딜 파이프라인 · 제안서 초안
  - DevAgent: GitHub PR · CI 상태 · 코드리뷰 브리핑
  - FinanceAgent: 지출결의서 · 예산 초과 검증 · 정산 배치
  - HRAgent: 휴가 승인 · 온보딩 체크리스트 · 계약 만료 알림
  - MarketingAgent: 캠페인 성과 · 콘텐츠 일정 · 카피 초안
- [ ] 개인 KPI 대시보드 UI
- [ ] 팀 대시보드·팀원별 리포트
- [ ] 5-신호 Urgency Engine (온보딩 프로필 + 사용 이력)
- [ ] 모바일 PWA
- [ ] 온프레미스 배포

---

## 11. 성공 지표 (KPI)

| 지표 | Phase 1 목표 | 6개월 목표 |
|---|---|---|
| 브리핑 생성 시간 | < 60초 | < 30초 |
| 명령 처리 성공률 | 80% | 90% |
| 분류 정확도 (사용자 피드백) | 75% | 90% |
| 월간 활성 사용자 | 500 | 5,000 |
| 유료 전환율 | 10% | 20% |

---

## 12. 경쟁 분석

| 서비스 | 강점 | 약점 | WhatToDo 차별점 |
|---|---|---|---|
| Superhuman | 이메일 UX | 이메일만 | 멀티소스 + 자연어 명령 |
| Notion AI | 문서 요약 | 능동적 수집 없음 | 자동 수집·tool 조합 |
| Motion | 일정 최적화 | AI 분류 부족 | 범용 업무 실행 |
| Slack AI | 채널 요약 | Slack 전용 | 채널 횡단 + 리포트 생성 |

---

## 13. 기능 추가 방법 — 확장 사이클

> Phase 2 이후 새 기능을 추가할 때는 아래 사이클을 반복한다.

```
① 업무 분석     → 반복성·원자성·LLM 필요 여부 체크
② Tool 설계     → 기존 tool 재사용 vs 신규, input/output 스키마 확정
③ 구현          → mock → 등록 → 실로직 → constraint 추가 (순서 중요)
④ 성능 평가     → tool 단위 테스트 + SubAgent tool 선택 정확도 측정
⑤ 프롬프트 업데이트 → 해당 SubAgent constraint에 새 제약만 추가
```

tool이 SubAgent당 10개 이상 누적되거나 선택 정확도가 저하되면 SubAgent를 추가 분리한다.
