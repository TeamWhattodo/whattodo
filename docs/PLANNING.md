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

## 2. 아키텍처 전환 전략

### Phase 1 — 단일 에이전트 + Tool Registry

단일 `WorkAssistantAgent`가 TOOL_REGISTRY에 등록된 tool을 자율 선택·조합해 모든 요청을 처리한다.

```
사용자 명령
    │
    ▼
[WorkAssistantAgent]  ← LLM Smart 티어, tool_use 루프
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

### Phase 2 — Orchestrator + SubAgents

tool이 누적되고 업무 유형이 다양해지면 Orchestrator가 요청을 전문 SubAgent에게 위임하는 구조로 전환한다.

```
사용자 명령
    │
    ▼
[Orchestrator]  ← LLM Smart 티어, 라우팅 전담
    │
    ├─► [BriefingAgent]   fetch + score + classify + finalize
    ├─► [ReportAgent]     parse_data + compute_stats + write_report
    ├─► [ActionAgent]     update_status + write_draft + send_reply
    └─► [SearchAgent]     search_items + search_docs (RAG)
    │
    ▼
Streamlit UI (변경 없음)
```

**전환 조건**: tool이 15개 이상 누적되거나, 단일 에이전트의 tool 선택 정확도가 저하될 때 전환한다. Phase 1 tool 코드는 SubAgent에 재배치만 하면 된다.

---

## 3. 커버 가능한 업무 및 Tool 분해

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
> - 벡터 DB: ChromaDB (로컬, 서버 불필요) / `backend/db/data/policy_store/`
> - 임베딩: `jhgan/ko-sroberta-multitask` (한국어 특화, 무료)
> - 문서 수집: `backend/scripts/ingest_policy.py` (신규 문서 추가 시 재실행)

#### 도메인 F — 분석 (Compute)

| Tool | 입력 | 출력 | LLM |
|---|---|---|---|
| `compute_daily_stats` | date | `DailyStats` | ❌ |
| `compute_kpi` | period | `KPIAggregated` | ❌ |
| `parse_billing_data` | file_path, month | `BillingData` | ❌ |

### 업무 → Tool 조합 패턴

에이전트 시스템 프롬프트에 포함해 tool 선택 정확도를 높인다.

| 업무 | Tool 조합 순서 |
|---|---|
| 복귀 브리핑 | fetch_emails → fetch_slack → fetch_calendar → score_urgency → classify_items → write_report(briefing) |
| 정산 리포트 | fetch_uploaded_file → parse_billing_data → compute_daily_stats → write_report(billing) |
| 답장 초안 | fetch_emails(filter) → get_item_thread → write_draft |
| 주간 결산 | search_past_items(7일) → compute_kpi → write_report(weekly) |
| 미팅 준비 | fetch_calendar_events → search_company_docs → write_meeting_agenda |
| 긴급 항목 파악 | fetch_emails → fetch_slack → score_urgency → filter_items(urgency≥4) |
| 사규 조회 | search_company_docs |
| 규정 기반 정산 검증 | parse_billing_data → search_company_docs → write_report(billing) |

---

## 4. 사용자 시나리오

### 시나리오 A — 월요일 아침 복귀 브리핑

```
사용자: "주말 동안 쌓인 것 정리해줘"

에이전트:
  → fetch_emails(since_hours=60)     [이메일 43건 수집]
  → fetch_slack_messages(since=60h)  [슬랙 187건 수집]
  → fetch_calendar_events(3일치)     [일정 5건]
  → score_urgency(전체 235건)        [레벨 1~5 분류]
  → classify_items(urgency≥3 항목)   [요약 + 액션 타입]
  → write_report(briefing)

결과: 브리핑 카드 표시
  🔴 지금 당장 (3건) — 계약서 서명, 배포 승인, 예산 승인
  🟡 오늘 안에 (7건) — 주간 회의 준비, 디자인 피드백 등
  ⚪ FYI (180건) — 접혀 있음
```

### 시나리오 B — 정산 리포트 작성

```
사용자: "5월 정산 리포트 작성해줘" (파일 업로드 포함)

에이전트:
  → fetch_uploaded_file(billing_may.csv)
  → parse_billing_data(month=2026-05)
  → compute_daily_stats(기간)
  → write_report(billing, data=...)

결과: 리포트 초안 Streamlit에 표시 → 다운로드 버튼
```

### 시나리오 C — 자연어 항목 처리

```
사용자: "박팀장 DM 답장 초안 써줘"

에이전트:
  → search_past_items(query="박팀장 DM", source=slack)
  → get_item_thread(item_id=...)
  → write_draft(tone=formal)

결과: 채팅창에 초안 표시 → 사용자 확인 후 복사
```

### 시나리오 D — 퇴근 전 일간 결산 (Phase 2)

```
스케줄 트리거 (오후 6시) 또는 사용자: "오늘 결산해줘"

에이전트:
  → search_past_items(오늘, status=done)
  → compute_daily_stats(오늘)
  → write_report(daily_summary)

결과: 결산 카드 표시
  ✅ 완료 7건 / 실제 48분
  ⏭ 이월 3건 → 내일 캘린더 블록 제안
```

### 시나리오 E — 사내 규정 조회 및 정산 검증 (Phase 2)

```
사용자: "출장 교통비 한도 얼마야?"

에이전트:
  → search_company_docs(query="출장 교통비 한도")

결과: "사내 규정(3.2절)에 따르면 출장 교통비 한도는 1일 5만원입니다."
```

```
사용자: "이 영수증 규정에 맞아?" (영수증 이미지 업로드)

에이전트:
  → parse_receipt(image_path="receipt.jpg")     [항목·금액 추출]
  → search_company_docs(query="식대 규정 한도")

결과: "식대 3만2천원 / 규정 한도 3만원 → 2천원 초과"
```

---

## 5. 기술 아키텍처

### Phase 1

```
┌─────────────────────────────────────┐
│         Streamlit (단일 앱)          │
│  메인: 브리핑 카드·체크리스트         │
│  사이드바: 채팅 인터페이스            │
└──────────────┬──────────────────────┘
               │ Python 직접 import
┌──────────────▼──────────────────────┐
│        WorkAssistantAgent            │
│   LLM Smart + TOOL_REGISTRY          │
│   tool_use 루프 (max 10 iter)        │
└──────┬───────────────────────────────┘
       │
┌──────▼──────────────────────────────┐
│           TOOL_REGISTRY              │
│  fetch / score / classify / write    │
│  update / search / compute           │
└──────┬──────────────────────────────┘
       │
┌──────▼──────────────────────────────┐
│           Data Layer                 │
│  TinyDB (JSON)  ·  heapq (Queue)    │
│  → Phase 2+: PostgreSQL + Redis      │
└─────────────────────────────────────┘
```

### Phase 2 (추가 레이어)

```
┌─────────────────────────────────────┐
│         Streamlit (변경 없음)        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│           Orchestrator               │
│   라우팅 전담 · LLM Smart            │
│   SubAgent 호출을 tool로 등록        │
└──────┬───────────────────────────────┘
       │
  ┌────┴──────────────────────────┐
  │            SubAgents           │
  ├─ BriefingAgent (Fast 티어)    │
  ├─ ReportAgent   (Fast 티어)    │
  ├─ ActionAgent   (Fast 티어)    │
  └─ SearchAgent   (Fast 티어)    │
       │
┌──────▼──────────────────────────────┐
│       기존 TOOL_REGISTRY 재사용      │
└─────────────────────────────────────┘
```

---

## 6. 데이터 모델 (공유 스키마)

```python
# backend/models.py — Week 1 전원 합의 후 확정

class WorkItem(BaseModel):
    id: str
    source: Literal["gmail", "slack", "calendar", "jira", "notion"]
    raw_content: str
    summary: str
    urgency_level: int              # 1~5
    urgency_breakdown: dict         # {"T": 0.78, ...}
    action_type: Literal["reply", "approve", "review", "fyi", "none"]
    due_at: datetime | None
    from_person: str | None
    status: Literal["pending", "done", "snoozed"]
    created_at: datetime
    completed_at: datetime | None
    actual_minutes: int | None

class WorkCard(BaseModel):          # UI 렌더링 전용 (WorkItem 경량화)
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
    stats: dict                     # total, urgent, fyi, estimated_minutes
    sections: dict                  # immediate, today, this_week, fyi
    contacts_needed: list[dict]
    summary_text: str
```

---

## 7. 개인정보 및 보안

- 이메일·메시지 원문은 처리 후 즉시 삭제, 요약본만 저장
- OAuth 토큰 암호화 저장 (AES-256)
- AI 처리는 Anthropic API (학습 미사용)
- 모든 발송 액션은 사용자 확인 필수 (가드레일)

---

## 8. 수익 모델

| 플랜 | 대상 | 가격 | 포함 내용 |
|---|---|---|---|
| Free | 개인 | 무료 | 소스 2개, 월 명령 30회 |
| Pro | 개인 | $9/월 | 소스 무제한, 명령 무제한, 파일 업로드 |
| Team | 팀 | $6/인/월 | Pro + 팀 대시보드, 관리자 리포트 |
| Enterprise | 기업 | 협의 | 온프레미스, SSO, 감사 로그 |

---

## 9. 개발 로드맵

### Phase 1 — 단일 에이전트 MVP (4주, ~2026-06-13)

#### 확정 범위

| 포함 | 제외 (Phase 2) |
|---|---|
| WorkAssistantAgent + TOOL_REGISTRY | Orchestrator + SubAgents |
| 도메인 A·B·C 핵심 tool (8개) | 도메인 E·F 고급 tool |
| Gmail + Slack + Calendar 커넥터 | Jira / Notion 커넥터 |
| Streamlit 혼합형 UI | 슬랙 봇 인터페이스 |
| Urgency Engine (T 신호) | 5-신호 가중합 |
| TinyDB 저장 | PostgreSQL 마이그레이션 |
| OAuth 인증 (Gmail, Slack) | Policy Engine |

#### 구현 3단계 순서

| 단계 | 기간 | 핵심 |
|---|---|---|
| 1단계 | Week 1 | mock_data로 tool 함수 파이프라인 동작 확인. LLM 없음. |
| 2단계 | Week 2 | 실데이터 연결 + `messages.create` 직접 호출로 LLM 응답 형식 파악. tool_use 아님. |
| 3단계 | Week 3~4 | tool_use 루프 전환. LLM이 tool 순서를 결정. |

#### 주차별 일정

```
Week 1 (파이프라인 스크립트)        Week 2 (실데이터 + LLM 직접 호출)
──────────────────────────────      ──────────────────────────────────
□ 환경 세팅, WorkItem 스키마 확정   □ Gmail OAuth 완료 → 실데이터 교체
□ mock_data로 fetch → score          □ classify에 LLM messages.create 추가
    → classify → WorkCard 출력       □ LLM 응답 형식 파악 + 파싱 패턴
□ Streamlit 기본 UI (mock)           □ Slack 커넥터
□ TOOL_REGISTRY 인터페이스 확정      □ write_draft 함수 구현

Week 3 (tool_use 에이전트 전환)     Week 4 (통합 & 마무리)
──────────────────────────────      ──────────────────────────────────
□ WorkAssistantAgent 구현            □ E2E 통합 테스트
□ tool_use 루프 + _dispatch 연결     □ 에러 처리 / 폴백
□ Calendar 커넥터                    □ 시스템 프롬프트 튜닝
□ Streamlit 채팅 사이드바 UI         □ 데모 시나리오 준비
□ 브리핑 카드 실데이터 렌더링        □ 버그 수정
```

#### 팀 역할 — 6인 구조

| # | 역할 | 담당 범위 |
|---|---|---|
| 팀장 | **Orchestrator + Frontend** | `agents/assistant_agent.py` (tool_use 루프), `agents/llm_client.py`, `app.py` Streamlit UI, `mock_data.py`, 스키마 확정 주도 |
| #2 | **Fetch Tools** | `tools/fetch.py`, `connectors/` 전체 (gmail/slack/calendar), `routers/auth.py` |
| #3 | **Score + Classify Tools** | `tools/scoring.py`, `tools/classify.py`, Urgency Engine 공식 구현 |
| #4 | **Write Tools** | `tools/write_report.py`, `tools/write_draft.py`, LLM Smart 프롬프트 설계 |
| #5 | **Action + Search Tools** | `tools/update_status.py`, `tools/search_items.py`, `tools/storage.py`, TinyDB CRUD |
| #6 | **Compute + Data Tools** | `tools/compute_stats.py`, `tools/parse_billing.py`, `backend/db/store.py`, `scheduler.py` |

```
의존성 흐름 (→ 는 "출력 스키마를 받아야 작업 가능")

#2 Fetch ──► 팀장 Agent ──► #3 Score/Classify ──► #4 Write
                              ▲                       ▲
                    스키마 Week 1 확정 (팀장 주도, 전원 참여)
#5 Action ◄──────────────────┘
#6 Compute ◄─────────────────┘
```

```
Week 1                    Week 2                    Week 3                    Week 4
──────────────────────    ──────────────────────    ──────────────────────    ──────────────
팀장 스키마 확정 주도      팀장 LLM 직접 호출 패턴   팀장 tool_use 루프        전원 통합·버그
     Streamlit 뼈대             classify 연결              _dispatch 구현         수정·데모
     mock_data 작성             채팅 사이드바 UI            시스템 프롬프트 튜닝

#2  mock fetch 구현       #2  Gmail OAuth 완료       #2  Slack 수집 완성       데모 시나리오
    (Gmail/Slack/Cal)          실데이터 교체               Calendar 완성          검증

#3  T신호 공식 구현        #3  5신호 뼈대 작성         #3  classify LLM 전환     단위 테스트

#4  write_report 뼈대     #4  LLM Smart 프롬프트      #4  write_draft 완성      리포트 형식
    (mock 데이터 기반)          설계·튜닝                   브리핑 헤더 연결       마무리

#5  storage CRUD 기초     #5  update_status 완성      #5  search_items 구현     Storage 완성

#6  DailyStats 공식       #6  compute_kpi 기초        #6  scheduler 크론 등록   parse_billing
```

> **Week 1 필수 합의 (팀장 주도, 전원 참여)**
> `WorkItem` · `WorkCard` · `BriefingResult` Pydantic 모델 확정
> → 각 담당자가 mock 데이터로 독립 개발 시작 가능

#### 브랜치 전략

```
main   ← 배포 가능 상태만. 주 1회 (금요일 데모 후) dev → main 병합
  └ dev ← 주간 통합 브랜치. PR 대상
      ├ feat/agent-core        (팀장)
      ├ feat/fetch-tools       (#2)
      ├ feat/score-classify    (#3)
      ├ feat/write-tools       (#4)
      ├ feat/action-search     (#5)
      └ feat/compute-data      (#6)
```

커밋 컨벤션: `feat:` / `fix:` / `chore:` / `docs:` / `test:`

---

### 기능 추가 방법 — 확장 사이클

> Phase 1 MVP 이후, 새 기능을 추가할 때는 아래 사이클을 반복한다.  
> 상세 절차(체크리스트·예시 포함)는 [WORKFLOW.md — 확장 사이클](WORKFLOW.md#확장-사이클--새-기능-추가-프로세스)을 참고한다.

```
① 업무 분석     → "이 업무를 커버해야 하는가?" (반복성·원자성·LLM 필요 여부 체크)
② Tool 설계     → 기존 tool 재사용 vs 신규 tool, input/output 스키마 확정
③ 구현          → mock → 등록 → 실로직 → 프롬프트 추가 (순서 중요)
④ 성능 평가     → tool 단위 테스트 + 에이전트 tool 선택 정확도 측정
⑤ 프롬프트 업데이트 → TOOL_PATTERNS 테이블에 새 업무 패턴 추가
```

tool이 15개 이상 누적되거나 tool 선택 정확도가 저하되면 Phase 2 (Orchestrator + SubAgents)로 전환한다.

---

### Phase 2 — Orchestrator + SubAgents (6주)

- [ ] Orchestrator 레이어 추가 (기존 Agent → BriefingAgent로 전환)
- [ ] ReportAgent, ActionAgent, SearchAgent 분리
- [ ] Jira / Linear 커넥터
- [ ] 일간 결산 자동화 (스케줄러)
- [ ] 주간 KPI 리포트 자동 생성
- [ ] Policy Engine (사내 규정 3-레이어)
- [ ] 사내 문서 RAG (`search_company_docs` tool)
  - 현재: PDF (`PyPDFLoader`)
  - 추후: Word (`Docx2txtLoader`), Markdown, HTML로 확장
  - 벡터 DB: ChromaDB (로컬) / 임베딩: `jhgan/ko-sroberta-multitask` (한국어 특화)
  - 파일: `backend/tools/policy_search.py`, `backend/db/data/policy_store/`, `backend/scripts/ingest_policy.py`
  - 사용자별 격리 컬렉션
- [ ] 슬랙 봇 인터페이스

### Phase 3 — 개인화 + 팀 기능 (6주)

- [ ] 개인 KPI 대시보드 UI
- [ ] 팀 대시보드 · 팀원별 리포트
- [ ] 5-신호 Urgency Engine (온보딩 프로필 + 사용 이력 기반)
- [ ] 사용 패턴 학습 (중요도 재조정)
- [ ] 모바일 PWA
- [ ] 온프레미스 배포

---

## 10. 성공 지표 (KPI)

| 지표 | Phase 1 목표 | 6개월 목표 |
|---|---|---|
| 브리핑 생성 시간 | < 60초 | < 30초 |
| 명령 처리 성공률 | 80% | 90% |
| 분류 정확도 (사용자 피드백) | 75% | 90% |
| 월간 활성 사용자 | 500 | 5,000 |
| 유료 전환율 | 10% | 20% |

---

## 11. 경쟁 분석

| 서비스 | 강점 | 약점 | WhatToDo 차별점 |
|---|---|---|---|
| Superhuman | 이메일 UX | 이메일만 | 멀티소스 + 자연어 명령 |
| Notion AI | 문서 요약 | 능동적 수집 없음 | 자동 수집·tool 조합 |
| Motion | 일정 최적화 | AI 분류 부족 | 범용 업무 실행 |
| Slack AI | 채널 요약 | Slack 전용 | 채널 횡단 + 리포트 생성 |
