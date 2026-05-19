# WhatToDo — 에이전트 워크플로우

## 구현 전략

| 단계 | 기간 | 핵심 목표 |
|---|---|---|
| **1단계** | Week 1 | mock_data로 tool 함수 파이프라인 동작 확인. LLM 없음. |
| **2단계** | Week 2 | 실데이터 연결 + `messages.create` 직접 호출로 LLM 응답 형식 파악. tool_use 아님. |
| **3단계** | Week 3~4 | tool_use 루프 전환. LLM이 tool 순서를 자율 결정. |
| **Phase 2** | 5주+ | Orchestrator + SubAgents 전환. 기존 tool 코드 재사용. |

> 팀원이 함수 파이프라인을 먼저 이해한 뒤 에이전트로 전환하는 방식.

---

## Phase 1 — 단일 에이전트 워크플로우

### 전체 흐름

```
사용자 명령 (자연어 or 버튼 클릭)
    │
    ▼
[WorkAssistantAgent]
    LLM Smart 티어 + TOOL_REGISTRY
    tool_use 루프 (max 10 iterations)
    │
    ├── Thought: 어떤 tool이 필요한가?
    │
    ├── Act: tool 호출 (에이전트가 자율 결정)
    │   ├─ fetch_emails / fetch_slack / fetch_calendar
    │   ├─ score_urgency
    │   ├─ classify_items
    │   ├─ write_report / write_draft
    │   ├─ update_item_status
    │   ├─ search_past_items
    │   └─ compute_daily_stats / compute_kpi
    │
    ├── Observe: tool 결과 확인
    │
    └── 반복 (결과가 충분할 때까지) → 최종 답변
    │
    ▼
Streamlit UI 업데이트
```

### 트리거 유형

```
A) 채팅 입력  — "정산 리포트 작성해줘", "긴급한 것만 알려줘"
B) 버튼 클릭  — [브리핑 시작] → "복귀 브리핑 실행해줘" 메시지로 변환
C) 카드 버튼  — [완료 체크] → "{item_id} 완료 처리해줘" 메시지로 변환
D) 스케줄     — APScheduler 크론 → 에이전트 직접 호출 (Phase 2)
```

모든 트리거가 동일한 `run_agent()` 루프를 통해 처리된다.

---

### 시나리오별 tool_use 흐름

#### A. 복귀 브리핑

```
User: "주말 동안 쌓인 것 정리해줘"

Iteration 1
  Thought: 이메일, 슬랙, 캘린더를 수집해야 한다.
  Act:     fetch_emails(since_hours=60, max_count=200)
  Observe: WorkItem[] 43건 반환

Iteration 2
  Act:     fetch_slack_messages(since_hours=60, mention_only=true)
  Observe: WorkItem[] 187건 반환

Iteration 3
  Act:     fetch_calendar_events(date_range=3)
  Observe: WorkItem[] 5건 반환

Iteration 4
  Thought: 수집 완료. 긴급도 계산이 필요하다.
  Act:     score_urgency(items=[...전체 235건...])
  Observe: ScoredItem[] 반환 (urgency_level 1~5 부여됨)

Iteration 5
  Thought: urgency 3 이상 항목에 액션 타입과 요약을 붙여야 한다.
  Act:     classify_items(items=[...urgency≥3인 55건...])
  Observe: ClassifiedItem[] 반환 (action_type, summary 포함)

Iteration 6
  Thought: 브리핑 리포트를 생성한다.
  Act:     write_report(report_type="briefing", data={...})
  Observe: BriefingResult 반환

Final:
  "주말 동안 235건이 수신됐습니다.
   🔴 지금 당장 처리 (3건): 계약서 서명, 배포 승인, 예산 승인
   🟡 오늘 안에 (7건): 주간 회의 준비 외 6건
   ⚪ FYI 225건은 접어두었습니다."
```

#### B. 정산 리포트 작성 (파일 업로드 포함)

```
User: "5월 정산 리포트 작성해줘" (billing_may.csv 첨부)

Iteration 1
  Act:     fetch_uploaded_file(file_path="billing_may.csv", file_type="csv")
  Observe: ParsedFile 반환

Iteration 2
  Act:     parse_billing_data(file_path="billing_may.csv", month="2026-05")
  Observe: BillingData {revenue: 4200만, refunds: 130만, net: 4070만}

Iteration 3
  Act:     compute_daily_stats(date="2026-05")
  Observe: DailyStats 반환

Iteration 4
  Act:     write_report(report_type="billing", data={...})
  Observe: ReportDraft 반환

Final: 리포트 초안 표시 + 다운로드 버튼
```

#### C. 답장 초안 작성

```
User: "박팀장 DM 답장 초안 써줘"

Iteration 1
  Act:     search_past_items(query="박팀장 DM", source="slack", date_range="7d")
  Observe: WorkItem[] 3건 반환

Iteration 2
  Act:     get_item_thread(item_id="slack_xxx", source="slack")
  Observe: ThreadItems[] (스레드 전체 맥락)

Iteration 3
  Act:     write_draft(item_id="slack_xxx", tone="formal")
  Observe: DraftText 반환

Final: 초안 표시 (사용자 확인 후 복사 → 직접 발송)
```

#### D. 긴급 항목만 파악

```
User: "긴급한 것만 알려줘"

Iteration 1
  Act:     fetch_emails(since_hours=8, max_count=50)
  Observe: WorkItem[] 12건

Iteration 2
  Act:     fetch_slack_messages(since_hours=8, mention_only=true)
  Observe: WorkItem[] 27건

Iteration 3
  Act:     score_urgency(items=[...39건...])
  Observe: ScoredItem[] (urgency 4~5: 4건)

Iteration 4
  Thought: urgency 4~5 항목만 분류한다.
  Act:     classify_items(items=[...urgency≥4인 4건...])
  Observe: ClassifiedItem[] 4건

Final: "긴급 항목 4건입니다.
  🔴 PROJ-402 배포 승인 대기 (마감 초과)
  🔴 박팀장 DM — 예산 승인 요청
  🟠 고객사 이메일 — 내일 오전 마감
  🟠 캘린더 — 오후 2시 회의 준비"
```

---

### 에러 처리

```python
# runner.py 에서 tool 에러 자동 처리
# 에이전트가 {"error": "..."} 결과를 받으면 시스템 프롬프트 지시에 따라:
#   1. 다른 tool로 대체 시도
#   2. 대체 불가 시 사용자에게 설명 후 중단
#   3. 동일 파라미터로 재시도 금지

소스 연결 실패:
  → {"error": "Gmail API 연결 실패"} 반환
  → 에이전트: "Gmail 연결에 실패했습니다. Slack과 Calendar로만 브리핑을 생성합니다."
  → 나머지 소스로 계속 진행

AI 분류 실패 (항목):
  → urgency=3, action_type="review" 기본값으로 처리
  → 사용자가 수동으로 재분류 가능

타임아웃 (>60초):
  → urgency 4~5 항목만 먼저 제시 (부분 브리핑)
  → 백그라운드에서 나머지 처리 후 갱신

max_iterations 초과:
  → "처리가 복잡합니다. 요청을 더 구체적으로 나눠서 다시 시도해주세요." 반환
```

---

## Phase 2 — Orchestrator + SubAgents 전환

### 전환 시점

- tool이 15개 이상 누적되어 단일 에이전트의 tool 선택 정확도 저하 시
- 또는 업무 유형별로 담당 팀원이 명확히 분리될 때

### 전환 방법

**기존 Phase 1 코드를 그대로 유지**하면서 Orchestrator 레이어만 추가한다. SubAgent는 Phase 1 tool을 그대로 import해 사용한다.

```
Phase 1 구조 (유지)
  tools/ ← 코드 변경 없음
  agents/runner.py ← SubAgent 내부 루프로 재사용

Phase 2 추가
  agents/orchestrator.py ← 신규
  agents/subagents/
      briefing_agent.py  ← runner.py + fetch/score/classify tool
      report_agent.py    ← runner.py + write/compute/parse tool
      action_agent.py    ← runner.py + update/draft tool
      search_agent.py    ← runner.py + search/rag tool
```

### Orchestrator 워크플로우

```
User: "정산 리포트 작성하고, 박팀장 DM 초안도 써줘"

[Orchestrator]
  Thought: 두 가지 업무다. ReportAgent와 ActionAgent에 위임한다.

  Act: call_report_agent(task="5월 정산 리포트 작성")
  Observe: ReportAgent 실행 결과 반환
    └─ [ReportAgent] (Fast 티어)
         fetch_uploaded_file → parse_billing_data → write_report
         결과: 리포트 초안 텍스트

  Act: call_action_agent(task="박팀장 DM 답장 초안 작성")
  Observe: ActionAgent 실행 결과 반환
    └─ [ActionAgent] (Fast 티어)
         search_past_items → get_item_thread → write_draft
         결과: 답장 초안 텍스트

Final: 두 결과를 취합해 사용자에게 전달
```

### SubAgent 구현 패턴

```python
# backend/agents/subagents/briefing_agent.py

BRIEFING_AGENT_TOOLS = [
    "fetch_emails", "fetch_slack_messages", "fetch_calendar_events",
    "score_urgency", "classify_items", "write_report",
]

BRIEFING_AGENT_SYSTEM = """
당신은 브리핑 전문 에이전트입니다.
이메일·슬랙·캘린더 수집 → 긴급도 계산 → 분류 → 브리핑 생성 업무만 담당합니다.
"""

def run_briefing_agent(task: str, **kwargs) -> dict:
    """
    Orchestrator의 tool 결과로 반환되는 함수.
    Phase 1 runner.py를 SubAgent 내부 루프로 재사용.
    SubAgent는 Fast 티어로 비용 절감.
    """
    # Fast 모델 + 도메인 한정 tool만 사용
    subset_registry = ToolRegistry()
    for name in BRIEFING_AGENT_TOOLS:
        subset_registry._tools[name] = registry._tools[name]

    final_text, _ = run_agent(
        user_message=task,
        history=[],
        model_override=settings.fast_model,   # Fast 티어
        registry_override=subset_registry,    # 도메인 한정 tool
    )
    return {"agent": "briefing", "result": final_text}
```

### Phase 2 팀 분업

| 담당 | 역할 |
|---|---|
| 팀장 | Orchestrator 구현 (`agents/orchestrator.py`), Streamlit UI 유지 |
| #2 | BriefingAgent 담당 (Phase 1 fetch tool 소유) |
| #3 | BriefingAgent 내 score/classify (Phase 1 코드 그대로) |
| #4 | ReportAgent 담당 (write tool 소유) |
| #5 | ActionAgent 담당 (action/search tool 소유) |
| #6 | SearchAgent + RAG (ChromaDB 벡터 스토어 추가) |

---

## 일간 결산 워크플로우 (Phase 2)

### 트리거

```
A) 스케줄 — 매일 오후 6시 (APScheduler)
B) 수동   — 사용자: "오늘 결산해줘"
```

### 에이전트 처리

```
User: "오늘 결산해줘"

[WorkAssistantAgent 또는 Phase 2: ActionAgent]

Iteration 1
  Act:     search_past_items(date_range="today", status="done")
  Observe: 완료 WorkItem[] 7건

Iteration 2
  Act:     search_past_items(date_range="today", status="pending")
  Observe: 이월 WorkItem[] 3건

Iteration 3
  Act:     compute_daily_stats(date="2026-05-13")
  Observe: DailyStats {completion_rate: 0.70, avg_response: 83min, ...}

Iteration 4
  Act:     write_report(report_type="daily_summary", data={...})
  Observe: DailySummary {narrative: "오늘 7건을 처리했습니다..."}

Final:
  ✅ 완료 7건 / 실제 48분
  ⏭ 이월 3건 (내일 마감 1건)
  완료율 70% / 평균 응답 83분
  "내일 오전 디자인 피드백 마감이 임박합니다."
```

---

## 주간 KPI 워크플로우 (Phase 2)

### 트리거

```
스케줄 — 금요일 오후 5시 (APScheduler)
```

### 에이전트 처리

```
[Scheduler → WorkAssistantAgent]

Iteration 1
  Act:     search_past_items(date_range="this_week")
  Observe: 이번 주 WorkItem[] 전체

Iteration 2
  Act:     compute_kpi(period="weekly")
  Observe: KPIAggregated {avg_completion: 0.82, overdue_ratio: 0.08, ...}

Iteration 3
  Act:     compute_kpi(period="last_weekly")     # 전주 비교용
  Observe: 지난주 KPIAggregated

Iteration 4
  Act:     write_report(report_type="kpi_weekly", data={current: ..., prev: ...})
  Observe: KPIReport {narrative: "이번 주 완료율 82%로 지난주 대비 +8%p..."}

Final: Streamlit 리포트 페이지 업데이트 + (선택) 슬랙 DM 발송
```

---

## Tool 추가 프로세스

새 기능을 추가할 때는 아래 순서를 따른다. 에이전트 로직은 건드리지 않는다.

```
1. 기능 제안
   팀원: "미팅 전에 안건 요약이 필요해요"

2. 업무 분해
   fetch_calendar_events → search_company_docs → write_meeting_agenda

3. tool 구현
   backend/tools/write_agenda.py 에 write_meeting_agenda() 함수 작성

4. registry 등록
   tool_registry.py 하단에 Tool() 등록

5. 시스템 프롬프트 업데이트
   prompts.py의 Tool 조합 패턴 테이블에 추가

6. 끝. 에이전트가 자동으로 활용.
```

### 신규 Tool 체크리스트

```
□ 함수 시그니처: 모든 파라미터 타입 명시
□ 반환 타입: JSON 직렬화 가능한 dict / list[dict]
□ 에러 처리: try-except → {"error": str(e)} 반환
□ 단독 테스트: mock 데이터로 독립 실행 가능
□ input_schema: Anthropic tool_use 스펙 준수
□ description: 에이전트가 언제 이 tool을 선택할지 명확히 기술
□ 등록: tool_registry.py에 registry.register() 추가
□ 패턴 추가: prompts.py Tool 조합 패턴 테이블 업데이트
```

---

## 데이터 흐름 다이어그램

### Phase 1

```
[사용자 입력]
    │
    ▼
[WorkAssistantAgent]  ← LLM Smart + TOOL_REGISTRY
    │
    ├─► fetch tools  ──────────────────────────┐
    │   (Gmail / Slack / Calendar / Jira)       │
    │                                           ▼
    ├─► score_urgency ◄──────────────── WorkItem[]
    │       │
    │       ▼ ScoredItem[]
    ├─► classify_items
    │       │
    │       ▼ ClassifiedItem[]
    ├─► write_report / write_draft
    │       │
    │       ▼ ReportDraft / DraftText
    ├─► update_item_status / compute_stats
    │       │
    │       ▼ UpdateResult / DailyStats
    │
    ▼
[TinyDB 저장]  ←── 각 tool이 완료 즉시 저장
    │
    ▼
[Streamlit 렌더링]
```

### Phase 2

```
[사용자 입력]
    │
    ▼
[Orchestrator]  ← LLM Smart, 라우팅 전담
    │
    ├─► call_briefing_agent ──► [BriefingAgent]  Fast 티어
    │                                │
    │                           fetch → score → classify → write
    │
    ├─► call_report_agent ────► [ReportAgent]    Fast 티어
    │                                │
    │                           parse → compute → write
    │
    ├─► call_action_agent ────► [ActionAgent]    Fast 티어
    │                                │
    │                           search → draft / update
    │
    └─► call_search_agent ────► [SearchAgent]    Fast 티어
                                     │
                                search_items / search_docs(RAG)
    │
    ▼ (각 SubAgent 결과 취합)
[Orchestrator 최종 답변]
    │
    ▼
[Streamlit 렌더링]  ← 변경 없음
```

---

## 시퀀스 다이어그램 — 복귀 브리핑 (Phase 1)

```
Streamlit    runner.py     LLM      fetch tool   score tool   classify tool   write tool   TinyDB
    │             │          │           │             │             │              │          │
    │─명령────►  │          │           │             │             │              │          │
    │             │─messages─►│          │             │             │              │          │
    │             │          │           │             │             │              │          │
    │             │◄─tool_use─│          │             │             │              │          │
    │             │  (fetch_emails)       │             │             │              │          │
    │             │─────────────────────►│             │             │              │          │
    │             │◄─────────────────────│             │             │              │          │
    │             │─tool_result──►│      │             │             │              │          │
    │             │              │       │             │             │              │          │
    │             │◄─tool_use────│       │             │             │              │          │
    │             │  (score_urgency)                   │             │              │          │
    │             │──────────────────────────────────►│             │              │          │
    │             │◄──────────────────────────────────│             │              │          │
    │             │─tool_result──►│                   │             │              │          │
    │             │              │                    │             │              │          │
    │             │◄─tool_use────│                    │             │              │          │
    │             │  (classify_items)                              │              │          │
    │             │───────────────────────────────────────────────►│              │          │
    │             │◄───────────────────────────────────────────────│              │          │
    │             │─tool_result──►│                               │              │          │
    │             │              │                               │              │          │
    │             │◄─tool_use────│                               │              │          │
    │             │  (write_report)                                              │          │
    │             │──────────────────────────────────────────────────────────►│          │
    │             │◄──────────────────────────────────────────────────────────│          │
    │             │─tool_result──►│                                           │          │
    │             │              │                                            │          │
    │             │◄─end_turn────│                                            │     ─저장─►│
    │◄─최종답변───│              │                                                        │
    │─렌더링──────────────────────────────────────────────────────────────────────────────│
```

---

## 확장 사이클 — 새 기능 추가 프로세스

새 업무를 에이전트에 추가할 때마다 이 5단계를 반복한다.  
팀원이 바뀌거나 기능이 늘어도 동일한 사이클을 적용하면 일관성이 유지된다.

```
① 업무 분석 → ② Tool/Agent 설계 → ③ 구현 → ④ 성능 평가 → ⑤ 시스템 프롬프트 업데이트
      └──────────────────────────────────────────────────────────────────────────────────┘
                                        반복
```

---

### ① 업무 분석

**목표**: "이 서비스로 어떤 업무를 커버할 것인가"를 정의한다.

추가 여부를 판단하는 체크리스트:

| 질문 | 기준 |
|---|---|
| 반복성 | 사용자가 주 3회 이상 할 만한 업무인가 |
| 원자성 | 더 작은 단위로 쪼갤 수 있는가 — 쪼개지면 각각 tool |
| LLM 필요성 | 의미 이해가 필요한가, 아니면 순수 코드로 처리 가능한가 |

**출력물 — 업무 명세서**

| 항목 | 내용 |
|---|---|
| 업무명 | 예: 미팅 전 안건 브리핑 |
| 트리거 | 예: "오후 2시 미팅 준비해줘" |
| 입력 | 예: 오늘 캘린더 일정 |
| 출력 | 예: 미팅별 안건 요약 + 관련 이메일/슬랙 맥락 |
| LLM 필요 여부 | 예: ✅ (요약 생성 시 필요) |

---

### ② Tool / Agent 설계

**목표**: 업무를 tool 단위로 분해하고 인터페이스를 확정한다.

결정해야 할 것:

| 질문 | 판단 기준 |
|---|---|
| 기존 tool 재사용 vs 신규 tool | 기존 tool의 output이 그대로 쓰이면 재사용 |
| tool 추가 vs SubAgent 신설 | 단일 에이전트 tool 수 20개 미만이면 tool 추가, 초과 시 SubAgent 분리 |
| tool 조합 순서 | 에이전트가 자율 결정하게 두되, 순서 제약이 있으면 시스템 프롬프트에 명시 |

**출력물 — Tool 명세서** (구현 시작 전 팀 합의 필수)

```python
{
    "name": "write_meeting_agenda",
    "description": "미팅 주제와 관련 맥락으로 안건 초안 생성",
    "input_schema": {
        "type": "object",
        "properties": {
            "meeting_title": {"type": "string"},
            "context":       {"type": "string"},  # 관련 이메일/슬랙 내용
        },
        "required": ["meeting_title"],
    },
    # output_type: str (AgendaText)
    # LLM: Smart 1-shot
    # 담당자: #3 Processing Tools
}
```

---

### ③ 구현

**순서가 중요하다.** 로직 구현보다 인터페이스 확인이 먼저다.

```
1. mock 함수 구현 (반환값 하드코딩)
       ↓
2. TOOL_REGISTRY 등록 → 에이전트가 tool을 선택하는지 확인
       ↓
3. 실제 로직 구현
       ↓
4. 시스템 프롬프트 Tool 패턴 테이블에 추가
```

1번을 먼저 하는 이유: 에이전트가 tool을 선택하지 않으면 `description` 문제, 선택했는데 결과가 이상하면 로직 문제다. 두 문제를 분리해서 디버깅할 수 있다.

```python
# 1단계: mock 함수
async def write_meeting_agenda(meeting_title: str, context: str = "") -> str:
    return f"[MOCK] {meeting_title} 안건: 논의 사항 1, 2, 3"  # 하드코딩

# 2단계: TOOL_REGISTRY에 등록 후 에이전트 테스트
assert "write_meeting_agenda" in extract_tool_calls(
    agent.chat("오후 2시 미팅 준비해줘")
)

# 3단계: 실제 로직으로 교체
async def write_meeting_agenda(meeting_title: str, context: str = "") -> str:
    return await llm_client.complete(AGENDA_PROMPT.format(...), tier="smart")
```

---

### ④ 성능 평가

두 레벨로 평가한다.

**Tool 레벨 (단위 테스트)**

```python
# tests/test_write_meeting_agenda.py
async def test_agenda_includes_title():
    result = await write_meeting_agenda("분기 리뷰", context="...")
    assert "분기 리뷰" in result

async def test_empty_context_returns_generic_agenda():
    result = await write_meeting_agenda("주간 회의")
    assert len(result) > 10
```

**Agent 레벨 (통합 평가)**

| 지표 | 측정 방법 |
|---|---|
| Tool 선택 정확도 | 정답 tool 조합 대비 실제 선택 일치율 |
| 불필요 tool 호출 | 정답 조합에 없는 tool을 추가 호출한 비율 |
| Iteration 수 | 평균 반복 횟수 (낮을수록 좋음) |
| 최종 답변 품질 | LLM-as-judge 점수 (1~5) |

```python
# tests/eval_agent_routing.py
TEST_CASES = [
    {
        "input":    "오후 2시 미팅 준비해줘",
        "expected": ["fetch_messages", "write_meeting_agenda"],
    },
    {
        "input":    "이 이메일 초안 써줘",
        "expected": ["write_draft"],
    },
]

for case in TEST_CASES:
    actual = extract_tool_calls(agent.chat(case["input"]))
    assert actual == case["expected"], f"Expected {case['expected']}, got {actual}"
```

**평가 결과에 따른 처리**

| 증상 | 원인 | 처치 |
|---|---|---|
| tool 선택 안 함 | description 불명확 | description 수정 |
| 순서 틀림 | 에이전트가 순서를 모름 | 시스템 프롬프트에 패턴 명시 |
| 불필요 호출 많음 | 종료 조건 불명확 | "충분한 정보가 있으면 추가 호출 금지" 강화 |
| 출력 품질 낮음 | tool 내부 프롬프트 문제 | tool 프롬프트 수정 |

---

### ⑤ 시스템 프롬프트 업데이트

평가 통과 후, 에이전트 시스템 프롬프트의 Tool 패턴 테이블에 새 업무를 추가한다.

```python
# agents/assistant_agent.py — SYSTEM_PROMPT 내 패턴 테이블
TOOL_PATTERNS = """
| 사용자 요청 패턴         | 사용할 tool 조합                                        |
|------------------------|-------------------------------------------------------|
| 브리핑 요청             | fetch_messages → score_urgency → classify_items → finalize_briefing |
| 초안 작성 요청          | write_draft                                           |
| 미팅 준비 요청          | fetch_messages(calendar) → write_meeting_agenda       |  ← 새로 추가
| 상태 조회 요청          | get_briefing_summary                                  |
| 완료/스누즈 처리        | update_item_status                                    |
"""
```

이 테이블이 에이전트의 "레시피 북"이다. 새 기능이 추가될수록 에이전트가 더 정확하게 tool을 조합한다.

---

### 사이클 예시 — "미팅 전 안건 브리핑" 추가

```
① 업무 분석
   반복성: 미팅 있는 날마다 → 주 3~5회 ✅
   입력:   오늘 캘린더 일정
   출력:   미팅별 안건 요약 + 관련 이메일/슬랙 맥락
   LLM:    ✅ (요약 생성 시 필요)

② Tool 설계
   재사용:  fetch_messages (source=calendar) ✅
   신규:    write_meeting_agenda(meeting_title, context) → AgendaText
   조합:    fetch_messages → write_meeting_agenda

③ 구현
   tools/write_agenda.py 작성 (mock → 등록 → 실로직 → 프롬프트 추가)

④ 평가
   테스트: "오후 2시 미팅 준비해줘"
   정답 조합: [fetch_messages, write_meeting_agenda]
   3회 실행, tool 선택 일치율 100% 확인

⑤ 시스템 프롬프트 업데이트
   TOOL_PATTERNS에 "미팅 준비 요청" 행 추가
```
