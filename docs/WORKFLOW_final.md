# WhatToDo — 에이전트 워크플로우

## 설계 원칙

```
Orchestrator  → "누가 할 건지" 결정 (intent 분류 + 라우팅)
SubAgent      → "어떻게 할 건지" 자율 결정 (도메인 내 tool_use 루프)
Tool          → "실제로 한 가지 일" 실행 (순수 함수)
```

**구조 패러다임**: Hierarchical Multi-Agent. Orchestrator(LLM Smart)가 상위에서 intent를 판단하고, SubAgent(LLM Fast)가 하위에서 도메인 내 tool을 자율 실행한다. 그래프는 라우팅 구조, tool_use 루프는 실행 구조로 분리된다.

```
LangGraph 그래프 (라우팅)     SubAgent 내부 (실행)
──────────────────────        ────────────────────
Orchestrator                  tool_use 루프
  ├─ BriefingAgent    →         Thought → Act → Observe
  ├─ ReportAgent      →         LLM이 tool 선택·순서 자율
  ├─ ActionAgent      →         constraint만 코드로 강제
  └─ SearchAgent      →
```

**agentic 설계의 핵심**: SubAgent 시스템 프롬프트는 tool 실행 순서(sequence)를 지정하지 않는다. 도메인 경계와 실행 제약(constraint)만 명시하고, 나머지는 LLM이 상황에 맞게 판단한다.

```
# 잘못된 방향 — 순서 고정 (스크립트형)
"fetch → score → classify → write 순서로 실행하세요."

# 올바른 방향 — 제약만 명시 (agentic)
"score는 반드시 fetch 완료 후 실행. write는 classify 완료 후 실행.
 이 외 순서와 tool 선택은 상황에 맞게 판단하세요."
```

---

## 구현 단계

| 단계 | 기간 | 핵심 목표 |
|---|---|---|
| **Phase 1** | Week 1~4 | 단일 에이전트 + TOOL_REGISTRY. 완료. |
| **Phase 2** | Week 5~10 | LangGraph Orchestrator + SubAgents 전환. |
| **Phase 3** | Week 11+ | Human-in-the-loop · Memory · 멀티턴 태스크. |

---

## Phase 1 — 단일 에이전트 (완료)

### 전체 흐름

```
사용자 명령 (자연어 or 버튼 클릭)
    │
    ▼
[WorkAssistantAgent]
    LLM Smart + TOOL_REGISTRY, tool_use 루프 (max 10)
    │
    ├── fetch_emails / fetch_slack / fetch_calendar
    ├── score_urgency
    ├── classify_items
    ├── write_report / write_draft
    ├── update_item_status
    ├── search_past_items
    └── compute_daily_stats / compute_kpi
    │
    ▼
Streamlit UI 업데이트
```

### 트리거 유형

```
A) 채팅 입력  — "정산 리포트 작성해줘", "긴급한 것만 알려줘"
B) 버튼 클릭  — [브리핑 시작] → "복귀 브리핑 실행해줘" 메시지로 변환
C) 카드 버튼  — [완료 체크] → "{item_id} 완료 처리해줘" 메시지로 변환
```

모든 트리거가 동일한 `run_agent()` 루프를 통해 처리된다.

---

## Phase 2 — LangGraph Orchestrator + SubAgents

### 전체 흐름

```
사용자 명령 or APScheduler
    │
    ▼
[LangGraph State 초기화]
WhatToDoState {
    user_input, intent, work_items,
    results, error, user_preferences,
    retry_count, has_write_output
}
    │
    ▼
[intent_classifier]   ← LLM Smart, 라우팅 전담
① intent 보정 (rule-based): 복합 의도 누락 시 자동 보정
    │
    ├─ "briefing" ──► [BriefingAgent]   Fast 티어, 도메인: fetch·score·classify·write
    ├─ "report"   ──► [ReportAgent]     Fast 티어, 도메인: parse·compute·write
    ├─ "action"   ──► [ActionAgent]     Fast 티어, 도메인: search·draft·update
    ├─ "search"   ──► [SearchAgent]     Fast 티어, 도메인: search·RAG
    ├─ "chat"     ──► [general_chat]    Fast 티어, 단순 Q&A
    └─ "A,B"      ──► Send API 병렬 실행 (복합 의도)
    │
② constraint check (rule-based): tool 실행 전 선후관계 검증
    │
    ▼
[collect_results]     ← 복합 의도 시 여러 SubAgent 결과 병합
    │
    ▼
[output_validator]    ← write_* 출력만 적용 · LLM Fast
③ 출력 품질 검증: is_sufficient 판단 → false 시 재시도 (max 2회)
    │
    ▼
Streamlit UI (변경 없음)
```

### intent_classifier (Orchestrator)

```python
ORCHESTRATOR_SYSTEM = """
당신은 업무 요청을 분류해 적합한 SubAgent에 라우팅합니다.

분류 기준:
- briefing : 부재 기간 정리, 복귀 브리핑, 긴급 항목 파악
- report   : 정산 리포트, 일간 결산, 주간 KPI, 파일 분석
- action   : 답장 초안 작성, 항목 완료·스누즈, 캘린더 블록 생성
- search   : 사내 규정 조회, 과거 항목 검색, 영수증 검증
- chat     : 위에 해당하지 않는 일반 질문

복합 의도(예: 영수증 검증 + 규정 조회)는 쉼표로 구분해 반환하세요.
예: "report,search"
"""
```

### SubAgent 시스템 프롬프트 원칙

각 SubAgent는 아래 구조를 따른다. **순서 지시 없음 — 제약만 명시.**

#### BriefingAgent

```python
BRIEFING_AGENT_TOOLS = [
    "fetch_emails", "fetch_slack_messages", "fetch_calendar_events",
    # Jira: MCP 툴 이름은 mcp-atlassian 서버 로드 후 확정
    "score_urgency", "classify_items", "write_report",
]

BRIEFING_AGENT_SYSTEM = """
당신은 브리핑 전담 에이전트입니다.
사용 가능한 tool: fetch_emails, fetch_slack_messages, fetch_calendar_events,
                  Jira MCP 툴, score_urgency, classify_items, write_report

제약:
- score_urgency는 반드시 fetch 완료 후 실행
- write_report는 반드시 classify 완료 후 실행
- 수집 결과가 0건이면 score/classify 생략 가능
- 소스 연결 실패 시 가능한 소스로만 진행하고 사용자에게 알림

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.
"""
```

#### ReportAgent

```python
REPORT_AGENT_TOOLS = [
    "fetch_uploaded_file", "parse_billing_data", "parse_receipt",
    "compute_daily_stats", "compute_kpi", "write_report",
]

REPORT_AGENT_SYSTEM = """
당신은 리포트 작성 전담 에이전트입니다.
사용 가능한 tool: fetch_uploaded_file, parse_billing_data, parse_receipt,
                  compute_daily_stats, compute_kpi, write_report

제약:
- parse_billing_data / parse_receipt는 fetch_uploaded_file 완료 후 실행
- write_report는 compute 계열 tool 완료 후 실행
- 파일이 없으면 fetch_uploaded_file 생략 가능

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.
"""
```

#### ActionAgent

```python
ACTION_AGENT_TOOLS = [
    "search_past_items", "get_item_thread",
    "write_draft", "update_item_status", "create_calendar_block",
]

ACTION_AGENT_SYSTEM = """
당신은 액션 처리 전담 에이전트입니다.
사용 가능한 tool: search_past_items, get_item_thread,
                  write_draft, update_item_status, create_calendar_block

제약:
- write_draft는 get_item_thread로 맥락 확보 후 실행 권장
- 발송·수정 액션(update_item_status)은 사용자 확인 후 실행
- create_calendar_block은 반드시 사용자 확인 후 실행

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.
"""
```

#### SearchAgent

```python
SEARCH_AGENT_TOOLS = [
    "search_past_items", "search_company_docs", "get_item_thread",
]

SEARCH_AGENT_SYSTEM = """
당신은 조회 전담 에이전트입니다.
사용 가능한 tool: search_past_items, search_company_docs, get_item_thread

제약:
- 사내 규정 질문은 search_company_docs 우선 사용
- 과거 항목 질문은 search_past_items 우선 사용
- 두 결과가 모두 필요하면 병렬 호출 가능

이 외 순서와 tool 선택은 상황에 맞게 판단하세요.
"""
```

### 시나리오별 실행 흐름

#### A. 복귀 브리핑

```
User: "주말 동안 쌓인 것 정리해줘"

[intent_classifier] → intent: "briefing"
[BriefingAgent] tool_use 루프 (자율 실행)
  → 소스 3개 fetch (순서·병렬 여부 자율)
  → score_urgency (fetch 완료 후)
  → classify_items (긴급도 기준 자율 필터)
  → write_report(briefing)

결과: "235건 수신. 🔴 지금 당장 3건 / 🟡 오늘 안에 7건 / ⚪ FYI 225건"
```

#### B. 정산 리포트

```
User: "5월 정산 리포트 작성해줘" (billing_may.csv 첨부)

[intent_classifier] → intent: "report"
[ReportAgent] tool_use 루프 (자율 실행)
  → fetch_uploaded_file
  → parse_billing_data (fetch 완료 후)
  → compute_daily_stats
  → write_report(billing) (compute 완료 후)

결과: 리포트 초안 + 다운로드 버튼
```

#### C. 답장 초안

```
User: "박팀장 DM 답장 초안 써줘"

[intent_classifier] → intent: "action"
[ActionAgent] tool_use 루프 (자율 실행)
  → search_past_items(query="박팀장 DM")
  → get_item_thread(맥락 확보)
  → write_draft(tone=formal)

결과: 초안 표시 (사용자 확인 후 복사)
```

#### D. 영수증 검증 (복합 의도)

```
User: "이 영수증 규정에 맞아?" (이미지 업로드)

[intent_classifier] → intent: "report,search"
[ReportAgent]  → parse_receipt(이미지) → ReceiptItem[식대 32,000원]
[SearchAgent]  → search_company_docs("식대 규정") → 한도 30,000원
[collect_results] → 두 결과 병합

결과: "식대 32,000원 / 규정 한도 30,000원 → 2,000원 초과"
```

#### E. 이월 항목 캘린더 등록

```
User: "이월된 것 내일 오전으로 잡아줘"

[intent_classifier] → intent: "action"
[ActionAgent]
  → search_past_items(status=snoozed)
  → [사용자 확인 요청] "이월 3건을 내일 09:00에 등록할까요?"
  → create_calendar_block (확인 후)

결과: 캘린더 블록 생성 완료
```

#### F. 일간 결산 (스케줄)

```
APScheduler 18:00 → run_agent("일간 결산 실행")

[intent_classifier] → intent: "report"
[ReportAgent] tool_use 루프 (자율 실행)
  → search_past_items(오늘, status=done)
  → search_past_items(오늘, status=pending)
  → compute_daily_stats
  → write_report(daily_summary)

결과: ✅ 완료 7건 / ⏭ 이월 3건 / 완료율 70%
```

### 에러 처리

```python
# 소스 연결 실패
→ {"error": "Gmail API 연결 실패"}
→ SubAgent: "Gmail 연결에 실패했습니다. Slack과 Calendar로만 진행합니다."
→ 나머지 소스로 계속 진행

# AI 분류 실패
→ urgency=3, action_type="review" 기본값 적용
→ 사용자가 카드에서 수동 재분류 가능

# 타임아웃 (> 60초)
→ urgency 4~5 항목만 부분 브리핑 제공
→ 백그라운드에서 나머지 처리 후 State 갱신

# max_iterations 초과
→ "요청이 복잡합니다. 더 구체적으로 나눠서 다시 시도해주세요."

# SubAgent 실패 (복합 의도)
→ 성공한 SubAgent 결과만 collect_results에 포함
→ 실패한 SubAgent는 error 필드에 기록
```

### APScheduler 연동

```python
# backend/scheduler.py
# LangGraph 그래프 외부에서 run_agent()를 직접 호출

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

@scheduler.scheduled_job("cron", hour=18, minute=0)
def daily_summary():
    run_agent("일간 결산 실행")

@scheduler.scheduled_job("cron", day_of_week="fri", hour=17, minute=0)
def weekly_kpi():
    run_agent("주간 KPI 리포트 생성")

scheduler.start()
```

---

## Harnessing — 3단계 검증

LLM 출력을 신뢰하지 않고 외부에서 강제 제어하는 구조. 비용과 지연을 최소화하기 위해 LLM 검증은 마지막 단계에만 적용한다.

```
[Orchestrator]
    ↓
① intent 보정 (rule-based, 비용 0)
  복합 의도 누락 보정 — 키워드 매칭으로 단일 intent를 복합으로 확장
    ↓
[SubAgent tool_use 루프]
    ↓ (각 tool 호출 전)
② constraint check (rule-based, 비용 0)
  순서 위반 차단 — score는 fetch 후, write는 classify 후
    ↓ (write_* tool 완료 후)
③ output_validator (LLM Fast, 최대 2회)
  is_sufficient → false 시 feedback 첨부해 재생성
    ↓
[Streamlit UI]
```

```python
# ① intent 보정
def validate_intent(intent: str, user_input: str) -> str:
    keywords = {
        "briefing": ["정리", "브리핑", "쌓인", "복귀", "출근"],
        "report":   ["리포트", "정산", "결산", "KPI", "작성"],
        "action":   ["초안", "답장", "완료", "처리", "잡아"],
        "search":   ["규정", "한도", "찾아", "검색", "얼마"],
    }
    matched = [k for k, words in keywords.items()
               if any(w in user_input for w in words)]
    if len(matched) > 1 and "," not in intent:
        return ",".join(matched)
    return intent

# ② constraint check
CONSTRAINTS = {
    "score_urgency":  {"requires": ["fetch_emails","fetch_slack_messages","fetch_calendar_events"]},
    "classify_items": {"requires": ["score_urgency"]},
    "write_report":   {"requires": ["classify_items"]},
    "write_draft":    {"requires": ["get_item_thread"]},
}

def check_constraint(tool_name: str, called_tools: list[str]) -> tuple[bool, str]:
    c = CONSTRAINTS.get(tool_name)
    if not c:
        return True, ""
    satisfied = any(t in called_tools for t in c["requires"])
    if not satisfied:
        return False, f"{tool_name} 실행 불가: {c['requires']} 중 하나가 먼저 필요"
    return True, ""

# ③ output_validator — write_draft · write_report에만 적용
VERIFY_PROMPT = """
다음 기준으로 출력을 평가하세요.
1. 사용자 요청에 직접 답했는가
2. 누락된 핵심 정보가 없는가
3. 사실 오류나 모순이 없는가
JSON: {"is_sufficient": bool, "feedback": "미흡 시만 기재"}
"""
```

---

## 복합 업무 처리 — Orchestrator 병렬 위임

Orchestrator가 Send API로 복수 SubAgent를 병렬 실행한다. 결과는 collect_results에서 병합.

```python
from langgraph.types import Send

def route_by_intent(state):
    intents = state["intent"].split(",")
    if len(intents) > 1:
        return [Send(i.strip(), state) for i in intents]  # 병렬
    return intents[0]
```

**주요 복합 업무 패턴**

| 요청 | 라우팅 | 방식 |
|---|---|---|
| "쌓인 것 정리하고 긴급한 것 답장 초안도 써줘" | briefing + action | 순차 (브리핑 결과 → 액션 입력) |
| "이 영수증 규정에 맞아?" | report + search | 병렬 |
| "오후 미팅 준비해줘" | briefing + search | 병렬 |
| "이번 주 마무리해줘" | report + action | 병렬 (결산 + 캘린더 등록) |
| "새로 합류했어, 뭐부터 봐야 해?" | search + briefing | 병렬 → 취합 |

---

## Phase 2 → Phase 3 전환

### Phase 3 추가 노드

#### Human-in-the-loop

```python
# LangGraph interrupt() — 발송 직전 사용자 승인

from langgraph.types import interrupt

def action_agent_node(state):
    draft = write_draft(...)
    # 발송 액션 전 중단, 사용자 확인 대기
    approved = interrupt({"message": "이 초안을 발송할까요?", "draft": draft})
    if approved:
        send_reply(draft)
    return {**state, "results": {...}}
```

#### DomainAgent 확장 (Phase 3)

온보딩 직군 선택 시 해당 DomainAgent 노드가 활성화된다. 기존 SubAgent 코드는 건드리지 않고 노드·엣지만 추가한다.

```python
# Phase 3 — 노드 추가만으로 확장
graph.add_node("sales",     sales_agent_node)    # CRM · 딜 파이프라인 · 제안서
graph.add_node("dev",       dev_agent_node)      # GitHub PR · CI · 코드리뷰
graph.add_node("finance",   finance_agent_node)  # 지출결의 · 예산 초과 · 배치 정산
graph.add_node("hr",        hr_agent_node)       # 휴가 승인 · 온보딩 · 계약 만료
graph.add_node("marketing", marketing_agent_node) # 캠페인 성과 · 카피 초안

def route_by_intent(state):
    # user_domain에 따라 DomainAgent 우선 라우팅
    domain_intents = DOMAIN_INTENTS.get(state["user_domain"], [])
    if state["intent"] in domain_intents:
        return state["user_domain"]  # DomainAgent로
    return state["intent"]           # 기존 4개 SubAgent
```

```python
# user_preferences를 State에 누적
# 모든 SubAgent가 동일한 선호 컨텍스트 공유

state["user_preferences"] = {
    "박팀장": {"tone": "formal"},
    "브리핑_제외_시간": ["화요일_오전"],
    "우선_소스": ["slack", "gmail"],
}
```

#### 멀티턴 태스크

```python
# LangGraph checkpointer — 태스크 상태 영속화

from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("tasks.db")
graph = graph.compile(checkpointer=checkpointer)

# 며칠에 걸친 태스크 재개
graph.invoke(state, config={"configurable": {"thread_id": "task_001"}})
```

---

## Tool 추가 프로세스

새 기능을 추가할 때는 아래 순서를 따른다.

```
1. 업무 분해
   "미팅 전 안건 브리핑 필요" →
   fetch_calendar_events → search_company_docs → write_meeting_agenda

2. tool 구현 (mock → 실로직)
   backend/tools/write_agenda.py

3. SubAgent 등록
   해당 도메인의 AGENT_TOOLS 리스트에 추가

4. constraint 추가 (필요한 경우만)
   "write_meeting_agenda는 fetch 완료 후 실행"
   순서 강제 지시는 추가하지 않음

5. 끝. SubAgent가 새 tool을 자율 활용.
```

### 신규 Tool 체크리스트

```
□ 함수 시그니처: 모든 파라미터 타입 명시
□ 반환 타입: JSON 직렬화 가능한 dict / list[dict]
□ 에러 처리: try-except → {"error": str(e)} 반환
□ 단독 테스트: mock 데이터로 독립 실행 가능
□ input_schema: Anthropic tool_use 스펙 준수
□ description: SubAgent가 언제 이 tool을 선택할지 명확히 기술
□ 등록: 해당 SubAgent TOOLS 리스트에 추가
□ constraint 검토: 실행 선후관계가 있으면 시스템 프롬프트 제약에만 추가
```

---

## 성능 평가

### Tool 레벨 (단위 테스트)

```python
async def test_briefing_agent_selects_fetch_first():
    """fetch 없이 score가 먼저 호출되면 안 된다."""
    calls = []
    result = await briefing_agent_node(mock_state)
    assert calls.index("fetch_emails") < calls.index("score_urgency")

async def test_briefing_agent_skips_classify_on_empty():
    """수집 결과 0건이면 classify 생략."""
    state = mock_state_with_empty_fetch()
    result = await briefing_agent_node(state)
    assert "classify_items" not in result["tool_calls"]
```

### Agent 레벨 (통합 평가)

| 지표 | 측정 방법 |
|---|---|
| intent 분류 정확도 | 정답 intent 대비 Orchestrator 분류 일치율 |
| tool 선택 정확도 | SubAgent 내 tool 선택이 제약을 위반하지 않은 비율 |
| 불필요 tool 호출 | 결과에 기여하지 않은 tool 호출 비율 |
| iteration 수 | 평균 반복 횟수 (낮을수록 좋음) |
| 최종 답변 품질 | LLM-as-judge 점수 (1~5) |

**평가 결과에 따른 처치**

| 증상 | 원인 | 처치 |
|---|---|---|
| intent 오분류 | Orchestrator 프롬프트 불명확 | 분류 기준 예시 보강 |
| 제약 위반 | constraint 미명시 | 해당 SubAgent constraint 추가 |
| 불필요 tool 호출 | 종료 조건 불명확 | "충분한 정보가 있으면 추가 호출 금지" 강화 |
| tool 미선택 | description 불명확 | tool description 수정 |
| 출력 품질 낮음 | tool 내부 프롬프트 문제 | tool 프롬프트 수정 |

---

## 온보딩 워크플로우

온보딩은 최초 1회 실행된다. MCP 커넥터 연결과 사내 문서 RAG ingest 두 흐름이 병렬로 진행되며, 둘 다 완료되어야 런타임이 활성화된다.

### MCP 커넥터 연결

```
STEP 1. 서비스 선택
  지원 커넥터: Gmail · Slack · Jira · Notion
  (추후 확장: Calendar · Linear · Confluence)

STEP 2. OAuth 인증
  각 서비스 authorization URL로 리다이렉트
  사용자 권한 승인 → authorization code 수신

STEP 3. 토큰 수신
  access_token · refresh_token 발급

STEP 4. 암호화 저장
  AES-256 암호화 → connectors/auth.py
  토큰 만료 시 refresh_token으로 자동 갱신

STEP 5. fetch tool 연결 확인
  since_hours=1 테스트 수집으로 연결 검증
  실패 시 사용자에게 재인증 안내
```

```python
# connectors/auth.py 구조 (예시)
SUPPORTED_CONNECTORS = ["gmail", "slack", "jira", "notion"]

def connect(service: str) -> str:
    """OAuth URL 생성 → 리다이렉트"""
    ...

def save_token(service: str, token: dict) -> None:
    """AES-256 암호화 후 저장"""
    ...

def get_token(service: str) -> dict:
    """복호화 반환, 만료 시 자동 갱신"""
    ...
```

### 사내 문서 RAG ingest

```
STEP 1. 문서 업로드
  지원 형식: PDF (현재) · DOCX · MD (추후)
  복수 파일 업로드 가능

STEP 2. 문서 로더
  PDF → PyPDFLoader
  DOCX → Docx2txtLoader (추후)
  MD → UnstructuredMarkdownLoader (추후)

STEP 3. 청크 분할
  RecursiveCharacterTextSplitter
  chunk_size=500, chunk_overlap=50

STEP 4. 임베딩 생성
  모델: jhgan/ko-sroberta-multitask (한국어 특화, 무료)
  쿼리 임베딩도 동일 모델 적용 (벡터 공간 일치)

STEP 5. ChromaDB 저장
  경로: backend/db/data/policy_store/
  신규 문서 추가 시 ingest_policy.py 재실행
  ChromaDB 비어 있으면 search_company_docs → 안내 문구 반환
```

```python
# backend/scripts/ingest_policy.py
def ingest(file_paths: list[str]) -> None:
    for path in file_paths:
        docs = load(path)                          # 로더 자동 선택
        chunks = splitter.split_documents(docs)    # 청크 분할
        embeddings = model.encode(chunks)          # ko-sroberta
        chroma.add(chunks, embeddings)             # 저장
```

### search_company_docs tool (런타임)

```python
# backend/tools/policy_search.py
def search_company_docs(query: str, top_k: int = 3) -> str:
    """
    사내 규정·문서에서 query와 관련된 내용을 검색해 반환한다.
    ChromaDB가 비어 있으면 안내 문구 반환.

    호출 주체:
    - SearchAgent: 사규 조회, 규정 확인
    - ReportAgent: 영수증 검증 시 규정 대조 (복합 의도)
    """
    if chroma.is_empty():
        return "등록된 사내 문서가 없습니다. 온보딩에서 문서를 업로드해 주세요."
    chunks = chroma.similarity_search(query, k=top_k)
    return "\n\n".join(chunk.page_content for chunk in chunks)
```

### 온보딩 완료 조건

```
필수: MCP 커넥터 1개 이상 연결 완료
선택: 사내 문서 업로드 (없으면 search_company_docs 비활성)

온보딩 완료 → 런타임 활성화
  fetch_* tool: 저장된 OAuth 토큰으로 실데이터 수집
  search_company_docs: ChromaDB에서 벡터 검색
```

### 파일 구조

```
backend/
  connectors/
    auth.py              ← OAuth 토큰 관리 (AES-256)
    gmail.py             ← Gmail fetch tool
    slack.py             ← Slack fetch tool
    jira.py              ← Jira fetch tool
    notion.py            ← Notion fetch tool
  tools/
    policy_search.py     ← search_company_docs tool
  db/
    data/
      policy_store/      ← ChromaDB 벡터 DB (자동 생성)
  scripts/
    ingest_policy.py     ← 온보딩 ingest 실행 스크립트
```
