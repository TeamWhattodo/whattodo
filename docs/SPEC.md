# WhatToDo — 기술 명세 (SPEC)

## 1. 기술 스택 선택 요약

| 영역 | 선택 | 비고 |
|---|---|---|
| 백엔드 프레임워크 | **FastAPI** | Django 대신 — native async, REST API |
| ASGI 서버 | **Uvicorn** | FastAPI 표준 서버 |
| DB | **TinyDB** | JSON 파일 기반, 별도 DB 서버 불필요 |
| 스케줄러 | **APScheduler** | 결산·KPI 크론 작업 |
| Priority Queue | **heapq** (MVP) | Python 내장, 추후 Redis 교체 가능 |
| 프론트엔드 | **Streamlit** | 에이전트 결과 표시 UI, Python으로만 구현 |
| AI | **Anthropic SDK / OpenAI SDK** | 공통 래퍼로 추상화, 환경 변수 1줄로 교체 |
| HTTP 클라이언트 | **httpx** | async, OAuth API 호출용 |
| OAuth | **authlib** | Gmail, Slack, Jira 연동 |

---

## 2. 백엔드

### 2-1. FastAPI 역할 (MVP 기준)

**MVP에서 FastAPI의 역할은 OAuth 콜백 수신 전용이다.**

Gmail·Slack OAuth는 리디렉션 콜백 URL이 HTTP 엔드포인트여야 하므로 FastAPI가 필요하다. 그 외 브리핑 파이프라인은 Streamlit이 백엔드 Python 모듈을 직접 import해 호출한다. HTTP 직렬화 없이 함수 호출로 처리되므로 REST 엔드포인트가 필요 없다.

```python
# app.py (Streamlit) — REST 호출 없이 직접 import
from backend.agents.orchestrator import run_briefing
from backend.db.store import update_item_status

if st.button("브리핑 시작"):
    result = asyncio.run(run_briefing(user_id="demo"))
```

브라우저 확장(Widget Phase)으로 전환 시 REST 엔드포인트를 추가한다. 백엔드 로직은 변경 없이 라우터만 추가하면 된다.

```python
# OAuth 콜백 — MVP에서 유일하게 필요한 FastAPI 엔드포인트
@app.get("/auth/gmail/callback")
async def gmail_callback(code: str): ...

@app.get("/auth/slack/callback")
async def slack_callback(code: str): ...
```

### 2-2. API 엔드포인트

**MVP — OAuth 콜백만 노출**

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/auth/gmail/callback` | Gmail OAuth 리디렉션 수신 |
| GET | `/auth/slack/callback` | Slack OAuth 리디렉션 수신 |
| GET | `/health` | 서버 상태 확인 |

**Widget Phase (브라우저 확장 전환 시 추가)**

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/briefing/start` | 브리핑 세션 시작 |
| GET | `/briefing/{session_id}` | 브리핑 결과 조회 |
| PATCH | `/items/{item_id}` | 항목 상태 변경 (완료/스누즈) |
| POST | `/items/{item_id}/draft` | 답장 초안 생성 |
| GET | `/summary/daily` | 일간 결산 조회 |
| GET | `/summary/weekly` | 주간 KPI 리포트 조회 |
| GET | `/policy` | 사내 규정 조회 |
| PUT | `/policy` | 사내 규정 수정 |

### 2-3. 디렉토리 구조

```
whattodo/
├── backend/
│   ├── main.py                  # FastAPI (OAuth 콜백 + health)
│   ├── config.py                # pydantic-settings 환경 변수
│   ├── models.py                # 공유 Pydantic 모델 (WorkItem, WorkCard, BriefingResult …)
│   ├── scheduler.py             # APScheduler 크론 등록
│   ├── mock_data.py             # UI 독립 개발용 샘플 데이터 (#6 전용)
│   │
│   ├── routers/
│   │   └── auth.py              # OAuth 콜백 수신 (MVP 유일한 라우터)
│   │
│   ├── tools/                   ← 순수 함수. "다음에 뭘 할지" 결정하지 않음. 단독 테스트 가능.
│   │   ├── fetch.py             # fetch_gmail / fetch_slack / fetch_calendar
│   │   ├── scoring.py           # calculate_urgency(item) → (level, breakdown)
│   │   ├── classify.py          # classify_item(item) → WorkCard  [LLM Fast 1-shot]
│   │   ├── storage.py           # TinyDB CRUD (save / get / update)
│   │   └── rag.py               # [Phase 2] search_context(query) → str  (ChromaDB)
│   │
│   ├── agents/                  ← LLM + tool_use 루프. 다음 도구를 스스로 선택.
│   │   ├── llm_client.py        # Provider 추상화 (Anthropic / OpenAI)
│   │   ├── briefing_agent.py    # 브리핑 에이전트 (TOOL_REGISTRY + tool_use 루프)
│   │   └── action_agent.py      # 답장 초안 생성 (on-demand)
│   │
│   ├── connectors/              ← 외부 API 클라이언트. tools/fetch.py 에서 호출됨.
│   │   ├── base.py
│   │   ├── gmail.py
│   │   ├── slack.py
│   │   ├── calendar.py
│   │   └── jira.py
│   │
│   ├── policy/
│   │   ├── engine.py            # 3-레이어 Policy Engine
│   │   ├── models.py            # PolicyConfig, HardOverride, Guardrail
│   │   └── policy.json
│   │
│   └── db/
│       ├── store.py             # storage.py의 하위 TinyDB 구현체
│       └── data/
│
├── app.py                       # Streamlit 진입점
├── pages/
│   ├── onboarding.py            # 최초 1회 컨텍스트 설정 (주요 인물·프로젝트)
│   ├── briefing.py              # 복귀 브리핑 화면
│   ├── daily_summary.py         # 일간 결산 화면
│   └── kpi_report.py            # KPI 리포트 화면
└── docs/
```

---

## 3. 데이터 저장 (TinyDB)

### 3-1. TinyDB를 선택한 이유

- JSON 파일에 직접 저장 → 별도 DB 서버 불필요
- `where()` 쿼리로 필터링 가능 (raw `json` 모듈 대비 편의성)
- 추후 PostgreSQL 마이그레이션 시 쿼리 패턴 재활용 가능

```python
from tinydb import TinyDB, Query

db    = TinyDB("backend/db/data/work_items.json")
items = db.table("work_items")
Item  = Query()

# 오늘 완료 항목 조회
done_today = items.search(
    (Item.status == "done") & (Item.completed_at >= today_start)
)
```

### 3-2. 테이블 구조

| 파일 | 테이블 | 주요 필드 |
|---|---|---|
| `work_items.json` | work_items | id, source, summary, urgency_level, urgency_breakdown, action_type, status, due_at, completed_at, actual_minutes, policy_applied |
| `briefings.json` | briefings | id, user_id, absence_start, absence_end, stats, summary_text |
| `daily_summaries.json` | daily_summaries | id, date, completion_rate, avg_response_minutes, overdue_count, by_source, carryover_items |
| `kpi_reports.json` | kpi_reports | id, period, period_start, period_end, aggregated, vs_prev_week, narrative, recommendations |
| `user_profile.json` | user_profile | key_people (name/email/tier), key_projects (name/priority), company_context |

---

## 4. AI 에이전트 + 툴 구성

### 4-1. Agent vs Tool — 구분 원칙

"다음에 뭘 할지 결정하지 않으면 Tool이다."

| 구분 | 판별 기준 |
|---|---|
| **Tool** | 입력 → 출력만. LLM 루프 없음. 단독 테스트 가능. |
| **Agent** | LLM의 `tool_use`를 통해 다음 도구를 스스로 선택. 루프 있음. |

| 구분 | 컴포넌트 | 파일 | LLM | 역할 |
|---|---|---|---|---|
| **Tool** | fetch | `tools/fetch.py` | ❌ | 소스별 메시지 수집 (connectors 래핑) |
| **Tool** | scoring | `tools/scoring.py` | ❌ | 정량 5-신호 긴급도 계산 |
| **Tool** | classify | `tools/classify.py` | ✅ Fast 1-shot | 액션 타입 분류 + 1~2줄 요약 |
| **Tool** | storage | `tools/storage.py` | ❌ | TinyDB CRUD |
| **Agent** | Briefing Agent | `agents/briefing_agent.py` | ✅ Smart (루프) | tool_use로 브리핑 파이프라인 조율 |
| **Agent** | Action Agent | `agents/action_agent.py` | ✅ Smart | 답장 초안 생성 (on-demand) |

> Urgency Engine → `tools/scoring.py` 재분류. 순수 Python 계산이므로 Tool.  
> Classifier + Summarizer → `tools/classify.py`로 통합. LLM 1회 호출로 완결되므로 Tool.  
> Orchestrator → `agents/briefing_agent.py` 대체. LLM이 도구 순서를 결정하는 Agent.

---

### 4-2. Urgency 공식 (scoring 툴)

#### MVP — T 신호 단독

마감 잔여 시간만으로 긴급도를 계산한다. 부재 기간 항목에 가장 즉각적인 판단 기준이며, 구현이 단순하고 근거 설명이 가능하다.

```
urgency_level = ceil(T × 5)   →  1~5
```

| 신호 | 측정 방법 |
|---|---|
| T (마감 잔여 시간) | 지수 감쇠. 초과=1.0, 24h 후=0.12, 없음=최대 0.6 |

#### 확장 — 5-신호 가중합

온보딩 프로필(A 신호)과 사용 이력(F 신호)이 충분히 쌓이면 가중합으로 전환한다.

```
urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S
urgency_level = ceil(urgency_score × 5)   →  1~5
```

| 신호 | 가중치 | 측정 방법 |
|---|---|---|
| T (마감 잔여 시간) | 0.35 | 지수 감쇠. 초과=1.0, 24h 후=0.12, 없음=최대 0.6 |
| A (발신자 중요도) | 0.25 | 온보딩 태깅 우선 → 서명 파싱 → 행동 추정 → 기본값 0.4 (Section 5-b 참고) |
| F (반복 추적) | 0.20 | 미응답 동일 발신자 수, log 스케일 |
| K (키워드) | 0.10 | 정규식. "urgent"=+0.9, "FYI"=−0.4 |
| S (소스·채널) | 0.10 | Slack DM=0.85, Jira blocker=0.90, 이메일 CC=0.35 |

#### A 신호 — 발신자 중요도 취득 방법 (확장 단계 적용)

온보딩 설정(Section 5-b)에서 등록한 주요 인물 정보를 우선 활용한다.  
미등록 발신자는 아래 순서로 fallback한다.

| 우선순위 | 방법 | 특징 |
|---|---|---|
| 1 | **온보딩 태깅** | 주요 인물 4단계(임원·팀장·동료·기타) 직접 등록. 가장 정확. |
| 2 | **이메일 서명 파싱** | 서명에서 "대표", "CEO", "팀장" 등 직함 키워드 감지. 무설정 자동. |
| 3 | **행동 기반 추정** | 과거 평균 응답 시간·내가 먼저 연락한 비율·메시지 빈도로 중요도 추정. 데이터 축적 후 정확도 향상. |
| — | **기본값** | 위 3가지 모두 해당 없으면 0.4 (unknown) |

---

### 4-3. Briefing Agent — tool_use 루프

Briefing Agent는 Anthropic SDK의 `tool_use`를 사용해 아래 도구를 스스로 조합한다.  
파이프라인 순서를 코드에 하드코딩하지 않는다.

**TOOL_REGISTRY — 에이전트가 호출할 수 있는 도구 목록**

```python
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
            "properties": {"item_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["item_ids"],
        },
    },
    {
        "name": "classify_items",
        "description": "긴급도 계산 완료 항목에 액션 타입과 요약 부여 (LLM Fast 1-shot)",
        "input_schema": {
            "type": "object",
            "properties": {"item_ids": {"type": "array", "items": {"type": "string"}}},
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
```

**tool_use 루프 골격**

```python
async def run(user_id: str, absence_days: int) -> BriefingResult:
    messages = [{"role": "user", "content": f"{absence_days}일 복귀 브리핑을 생성해줘."}]
    while True:
        response = await client.messages.create(
            model=_model("smart"), tools=TOOL_REGISTRY, messages=messages,
        )
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _dispatch(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
            messages += [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": results},
            ]
```

---

### 4-4. LLM Provider 추상화

에이전트·툴 코드는 어떤 SDK를 쓰는지 몰라도 됩니다. `llm_client.complete()`만 호출하면 환경 변수에 따라 Anthropic 또는 OpenAI로 라우팅됩니다.

```
LLM_PROVIDER=anthropic  →  Anthropic SDK 호출
LLM_PROVIDER=openai     →  OpenAI SDK 호출
```

**티어 → 실제 모델 매핑**

| 티어 | Anthropic | OpenAI |
|---|---|---|
| Fast | claude-haiku-4-5-20251001 | gpt-4o-mini |
| Smart | claude-sonnet-4-6 | gpt-4o |

**추상화 계층 위치**

```
tools/classify.py
agents/briefing_agent.py      →  agents/llm_client.py  →  anthropic SDK
agents/action_agent.py                                  →  openai SDK
```

`llm_client.py`는 `complete(prompt, tier)` 인터페이스 하나만 외부에 노출합니다.  
SDK 교체 시 이 파일만 수정하면 됩니다.

---

## 5. Policy Engine (사내 규정)

### 5-1. 3-레이어 구조

```
[수집 항목]
    │
    ▼ L1. Hard Override  — AI 전, policy.json 규칙으로 urgency/action 강제 설정
    │
    ▼ Urgency Engine + Classifier  ← L2. 시스템 프롬프트에 회사 규정 컨텍스트 주입
    │
    ▼ L3. Guardrail  — AI 후, 특정 액션 무조건 차단 + 감사 로그
    │
    ▼ [UI 카드]
```

### 5-2. policy.json 구조

```json
{
  "company_name": "주식회사 예시",
  "communication_rules": "외부 파트너에게는 반드시 경어체 사용",
  "reporting_structure": "계약 관련 사안은 법무팀장 cc 필수",
  "project_priorities": "Project-Alpha는 이번 분기 최우선",

  "hard_overrides": [
    {
      "name": "VIP_고객_즉시처리",
      "condition": { "senders": ["cto@bigclient.com"] },
      "action": { "urgency_level": 5 }
    },
    {
      "name": "보안_이슈_강제리뷰",
      "condition": { "jira_labels": ["security", "compliance"] },
      "action": { "urgency_level": 5, "action_type": "review" }
    }
  ],

  "guardrails": [
    {
      "name": "자동_발송_금지",
      "condition": { "auto_send": true },
      "blocks": "send",
      "reason": "모든 발송은 사용자 확인 후 진행"
    },
    {
      "name": "계약_자동승인_금지",
      "condition": { "action_type": "approve", "keywords": ["계약서"] },
      "blocks": "approve",
      "reason": "계약 관련 승인은 사람이 직접 처리"
    }
  ]
}
```

---

## 5-b. 사용자 온보딩 — 컨텍스트 설정

사내 DB 연동 없이 발신자 중요도(A 신호)를 계산하고 브리핑 에이전트에 조직 컨텍스트를 제공하기 위해, 사용자가 온보딩 시 핵심 정보를 직접 입력한다.

### 온보딩 입력 항목

| 항목 | 설명 | 활용 신호 |
|---|---|---|
| 주요 인물 | 이름, 이메일, 직급(임원/팀장/동료/기타) | A 신호: 임원=0.95, 팀장=0.80, 동료=0.60, 기타=0.40 |
| 주요 프로젝트 | 프로젝트명, 우선순위(high/mid/low) | K 신호 보강 |
| 회사 기본 정보 | 회사명, 부서, 업무 언어 | 브리핑 에이전트 시스템 프롬프트 |

### MVP 구현 방식 — 구조화 온보딩

```python
# backend/db/data/user_profile.json 저장 구조
{
  "key_people": [
    {"name": "김대표", "email": "ceo@example.com", "tier": "exec"},
    {"name": "박팀장", "email": "lead@example.com", "tier": "lead"}
  ],
  "key_projects": [
    {"name": "Project-Alpha", "priority": "high"}
  ],
  "company_context": "SaaS 스타트업, 30명 규모"
}
```

**활용 위치**

1. `tools/scoring.py` — A 신호 계산 시 `user_profile.key_people` 조회
2. `agents/briefing_agent.py` — 시스템 프롬프트에 `company_context` + `key_projects` 주입

**Streamlit 진입점**: `pages/onboarding.py` — 최초 1회 설정 (재설정 가능)

### Phase 2 — RAG (비정형 문서 지원)

MVP 이후 사내 위키·정책 문서 등 비정형 문서가 늘어나면 벡터 검색으로 확장한다.

| 단계 | 구현 |
|---|---|
| 문서 업로드 | Streamlit 파일 업로드 → 청크 분할 → 임베딩 생성 |
| 저장 | ChromaDB (로컬 파일 기반, 서버 불필요) |
| 검색 | `tools/rag.py` — `search_context(query) → str` |
| 통합 | `briefing_agent.py` TOOL_REGISTRY에 `search_context` 도구 추가 |

```python
# Phase 2 스텁: tools/rag.py
def search_context(query: str) -> str: ...
```

> MVP 의존성 없음. Phase 2 시작 전까지 스텁만 유지.

---

## 6. 스케줄러

```python
# scheduler.py
scheduler.add_job(run_daily_summary, "cron", hour=18, minute=0)
scheduler.add_job(run_weekly_kpi,    "cron", day_of_week="fri", hour=17, minute=0)
scheduler.add_job(run_morning_brief, "cron", hour=8,  minute=30)  # 선택
```

---

## 7. 패키지 목록

```toml
# pyproject.toml
[project]
name = "whattodo"
requires-python = ">=3.11"
dependencies = [
    # 백엔드
    "fastapi",
    "uvicorn[standard]",
    # 프론트엔드
    "streamlit",
    # DB
    "tinydb",
    # 스케줄러
    "apscheduler",
    # AI — 둘 다 설치, LLM_PROVIDER 환경 변수로 선택
    "anthropic",
    "openai",
    # HTTP / OAuth
    "httpx",
    "authlib",
    # 설정
    "pydantic-settings",      # .env → Config 클래스
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",                  # FastAPI TestClient용
]
```

```bash
# 백엔드 실행
uv run uvicorn backend.main:app --reload

# Streamlit UI 실행
uv run streamlit run app.py
```

---

## 8. 환경 변수

```bash
# .env

# LLM Provider 선택 (anthropic | openai)
LLM_PROVIDER=anthropic

# Anthropic
ANTHROPIC_API_KEY=

# OpenAI (LLM_PROVIDER=openai 시 사용)
OPENAI_API_KEY=

# 모델 티어 매핑 — Provider 교체 시 이 두 줄만 변경
FAST_MODEL=claude-haiku-4-5-20251001   # openai: gpt-4o-mini
SMART_MODEL=claude-sonnet-4-6          # openai: gpt-4o

# OAuth — Gmail
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=

# OAuth — Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# OAuth — Google Calendar
GOOGLE_CALENDAR_CLIENT_ID=
GOOGLE_CALENDAR_CLIENT_SECRET=

# OAuth — Jira
JIRA_API_TOKEN=
JIRA_BASE_URL=

# 앱 설정
SECRET_KEY=
STREAMLIT_PORT=8501

# Urgency Engine 가중치 (조정 가능)
URGENCY_WEIGHT_TIME=0.35
URGENCY_WEIGHT_AUTHORITY=0.25
URGENCY_WEIGHT_FOLLOWUP=0.20
URGENCY_WEIGHT_KEYWORD=0.10
URGENCY_WEIGHT_SOURCE=0.10

# 파이프라인 설정
COLLECTION_LIMIT_PER_SOURCE=200
BRIEFING_TIMEOUT_SECONDS=60
CLASSIFIER_BATCH_SIZE=50
DEFAULT_ABSENCE_THRESHOLD_HOURS=8

# ReAct 설정
REACT_MAX_ITERATIONS=5
REACT_URGENCY_THRESHOLD=5
```

---

## 9. 팀 협업 설정

### 6인 1인 1에이전트 담당

| # | 담당 | 브랜치 | 핵심 파일 |
|---|---|---|---|
| 1 | **Briefing Agent** | `feat/briefing-agent` | `agents/briefing_agent.py`, `models.py`, `scheduler.py` |
| 2 | **Gmail Fetch Tool** | `feat/gmail-tool` | `tools/fetch.py` (gmail), `connectors/gmail.py`, `routers/auth.py` |
| 3 | **Slack + Calendar Fetch Tool** | `feat/slack-calendar-tool` | `tools/fetch.py` (slack/cal), `connectors/slack.py`, `connectors/calendar.py` |
| 4 | **Scoring Tool** | `feat/scoring-tool` | `tools/scoring.py` |
| 5 | **Classify + Storage Tool** | `feat/classify-tool` | `tools/classify.py`, `tools/storage.py` |
| 6 | **Streamlit UI** | `feat/streamlit-ui` | `app.py`, `pages/` 전체, `mock_data.py` |

### 브랜치 전략

```
main  ← 배포 가능 상태만. 주 1회 (금요일) dev → main 병합
  └ dev  ← 주간 통합 브랜치. PR 대상
      ├ feat/briefing-agent
      ├ feat/gmail-tool
      ├ feat/slack-calendar-tool
      ├ feat/scoring-tool
      ├ feat/classify-tool
      └ feat/streamlit-ui
```

### 커밋 컨벤션

```
feat:  새 기능
fix:   버그 수정
chore: 빌드·설정·의존성
docs:  문서
test:  테스트
```

### Week 1 필수 합의 — 데이터 스키마 (담당 #1 주도)

Streamlit(#6)이 mock 데이터로 독립 개발하려면 Week 1 내에 확정해야 한다.  
백엔드 담당(#2~#5)은 이 스키마를 출력 포맷으로 준수한다.

```python
# backend/models.py — 전원 공유 Pydantic 모델
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class WorkCard(BaseModel):
    id: str
    source: Literal["gmail", "slack", "calendar"]
    summary: str
    urgency_level: int                 # 1~5
    urgency_breakdown: dict            # {"T": 0.78, "A": 0.80, ...}
    action_type: Literal["reply", "approve", "review", "fyi", "none"]
    from_person: str
    received_at: datetime
    estimated_minutes: int
    due_at: datetime | None
    status: Literal["pending", "done", "snoozed"]

class BriefingHeader(BaseModel):
    briefing_id: str
    absence_days: int
    total: int
    urgent: int
    estimated_minutes: int
    contacts_needed: list[dict]        # {person, reason, channel}
    summary_text: str
```

### MVP 주차별 체크포인트

| 주차 | 완료 기준 |
|---|---|
| Week 1 | 스키마 확정, Gmail OAuth 로그인 성공, FastAPI `/health` 응답, Streamlit 앱 로컬 실행 |
| Week 2 | Gmail 수집 → Urgency Engine 점수 출력 → REST API로 `WorkCard` 1건 조회 확인 |
| Week 3 | Slack·Calendar 포함 전체 파이프라인 E2E, Streamlit에 카드 목록 표시 |
| Week 4 | 체크 완료 인터랙션, 에러 폴백, 브리핑 헤더 표시, 데모 시나리오 통과 |

---

## 10. 주요 설계 결정 (ADR 요약)

| 결정 | 선택 | 대안 | 이유 |
|---|---|---|---|
| MVP UI 방식 | Streamlit → Python 함수 직접 호출 | REST 폴링 | HTTP 레이어 제거, 서버 1개, 디버깅 단순 |
| Widget Phase | 브라우저 확장 → FastAPI REST | Streamlit 유지 | 실제 위젯 UX, 백엔드 재사용, FastAPI 라우터만 추가 |
| 긴급도 계산 | MVP: T 신호 단독 / 확장: 5-신호 가중합 | LLM 판단 | MVP는 마감 시간만으로 단순·명확. 확장 시 온보딩 프로필·사용 이력 활용 |
| ReAct 범위 | 긴급도 5 항목만 | 전체 항목 | 비용·시간 최적화, 나머지는 DAG로 충분 |
| DB | TinyDB (JSON) | PostgreSQL | 서버 불필요, MVP 충분. 스키마 동일하게 유지해 추후 마이그레이션 용이 |
| 사내 규정 | 3-레이어 Policy Engine | 프롬프트만 사용 | 규정 위반 보장 (가드레일), 감사 로그, 회사별 설정 파일 분리 |
| LLM Provider | 추상화 래퍼 (Fast/Smart 티어) | SDK 직접 호출 | Anthropic ↔ OpenAI 교체 시 llm_client.py 1개 파일만 수정 |
| Agent vs Tool 구분 | `tools/` = 순수 함수, `agents/` = tool_use 루프 | 파이프라인 직접 구현 | 역할 명확화, 단독 테스트 가능, 새 도구 등록이 파이프라인 코드 수정 없이 가능 |
| 온보딩 방식 | 구조화 폼 입력 → TinyDB 저장 (MVP) / RAG (Phase 2) | LLM이 메시지 패턴으로 자동 추론 | A 신호 정확도 보장. RAG는 비정형 문서가 늘어나는 Phase 2에서 `tools/rag.py`로 추가 |
