# WhatToDo — 기술 명세 (SPEC)

## 1. 기술 스택 선택 요약

| 영역 | 선택 | 비고 |
|---|---|---|
| 백엔드 프레임워크 | **FastAPI** | Django 대신 — native async, WebSocket 내장 |
| ASGI 서버 | **Uvicorn** | FastAPI 표준 서버 |
| DB | **TinyDB** | JSON 파일 기반, 별도 DB 서버 불필요 |
| 스케줄러 | **APScheduler** | 결산·KPI 크론 작업 |
| Priority Queue | **heapq** (MVP) | Python 내장, 추후 Redis 교체 가능 |
| 프론트엔드 | **React + Vite** | 위젯 컴포넌트 구조에 적합 |
| AI | **Anthropic SDK** (async) | Claude Haiku / Sonnet 혼용 |
| HTTP 클라이언트 | **httpx** | async, OAuth API 호출용 |
| OAuth | **authlib** | Gmail, Slack, Jira 연동 |

---

## 2. 백엔드

### 2-1. FastAPI를 선택한 이유

Django는 기본이 동기(sync) 프레임워크다. WebSocket 스트리밍을 위해 Django Channels를 얹으면 복잡도가 크게 올라가고, 이 서비스에서 Django의 장점(ORM, Admin 등)은 쓰지 않는다.

FastAPI는 네이티브 async로 WebSocket 스트리밍을 간결하게 구현할 수 있다.

```python
@app.websocket("/briefing/{session_id}")
async def stream_briefing(websocket: WebSocket, session_id: str):
    await websocket.accept()
    async for card in process_items(session_id):
        await websocket.send_json(card)
```

### 2-2. API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/briefing/start` | 복귀 브리핑 세션 시작 |
| WS | `/briefing/{session_id}` | 분류된 카드 실시간 스트리밍 |
| GET | `/briefing/{session_id}` | 브리핑 결과 조회 |
| PATCH | `/items/{item_id}` | 항목 상태 변경 (완료/스누즈) |
| POST | `/items/{item_id}/draft` | 답장 초안 생성 |
| GET | `/summary/daily` | 일간 결산 조회 |
| GET | `/summary/weekly` | 주간 KPI 리포트 조회 |
| GET | `/policy` | 사내 규정 조회 |
| PUT | `/policy` | 사내 규정 수정 |
| POST | `/auth/{provider}` | OAuth 인증 시작 (gmail, slack, jira …) |

### 2-3. 디렉토리 구조

```
whattodo/
├── backend/
│   ├── main.py                  # FastAPI 앱, 라우터 등록, 스케줄러 시작
│   ├── routers/
│   │   ├── briefing.py          # 브리핑 WebSocket + REST
│   │   ├── items.py             # 항목 상태 변경, 초안 생성
│   │   ├── summary.py           # 일간 결산 API
│   │   ├── kpi.py               # 주간/월간 KPI 리포트 API
│   │   ├── policy.py            # 사내 규정 CRUD
│   │   └── auth.py              # OAuth 인증 흐름
│   ├── agents/
│   │   ├── orchestrator.py      # 전체 파이프라인 제어
│   │   ├── urgency_engine.py    # 정량 5-신호 계산 (LLM 없음)
│   │   ├── classifier.py        # Haiku: 액션 타입 + 요약
│   │   ├── react_agent.py       # 긴급도 5 전용 ReAct 루프
│   │   └── summarizer.py        # Sonnet: 브리핑 헤더 생성
│   ├── connectors/
│   │   ├── base.py              # 커넥터 추상 클래스
│   │   ├── gmail.py
│   │   ├── slack.py
│   │   ├── calendar.py
│   │   └── jira.py
│   ├── policy/
│   │   ├── engine.py            # 3-레이어 Policy Engine
│   │   ├── models.py            # PolicyConfig, HardOverride, Guardrail
│   │   └── policy.json          # 사용자 규정 데이터
│   ├── db/
│   │   ├── store.py             # TinyDB 래퍼 (테이블별 접근)
│   │   └── data/
│   │       ├── work_items.json
│   │       ├── briefings.json
│   │       ├── daily_summaries.json
│   │       └── kpi_reports.json
│   ├── scheduler.py             # APScheduler 크론 등록
│   └── config.py                # pydantic-settings 환경 변수
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BriefingWidget.tsx
│   │   │   ├── WorkCard.tsx
│   │   │   ├── HeaderCard.tsx
│   │   │   ├── ContactPanel.tsx
│   │   │   └── DailySummaryPanel.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   └── vite.config.ts
└── docs/
    ├── PLANNING.md
    ├── WORKFLOW.md
    └── SPEC.md
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

---

## 4. AI 에이전트 구성

### 4-1. 역할 분리

| 컴포넌트 | 모델 | 역할 | LLM 사용 여부 |
|---|---|---|---|
| Urgency Engine | — | 정량 5-신호 긴급도 계산 | ❌ 순수 Python |
| Classifier | claude-haiku-4-5-20251001 | 액션 타입 분류 + 1~2줄 요약 | ✅ (~200 토큰/항목) |
| ReAct Agent | claude-sonnet-4-6 | 긴급도 5 항목 교차 참조 수집 | ✅ (최대 5회 반복) |
| Summarizer | claude-sonnet-4-6 | 브리핑 헤더·통계 문구 생성 | ✅ (전체 완료 후 1회) |
| Action Agent | claude-sonnet-4-6 | 답장 초안 생성 | ✅ (on-demand) |
| Daily Narrative | claude-haiku-4-5-20251001 | 일간 결산 코멘트 (~300 토큰) | ✅ |
| KPI Narrative | claude-sonnet-4-6 | 주간 KPI 분석 코멘트 (~500 토큰) | ✅ |

### 4-2. Urgency Engine 공식

```
urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S
urgency_level = ceil(urgency_score × 5)   →  1~5
```

| 신호 | 가중치 | 측정 방법 |
|---|---|---|
| T (마감 잔여 시간) | 0.35 | 지수 감쇠. 초과=1.0, 24h 후=0.12, 없음=최대 0.6 |
| A (발신자 권한) | 0.25 | 조직 계층 거리. CEO=1.0, 동료=0.5, 외부 클라이언트=0.75 |
| F (반복 추적) | 0.20 | 미응답 동일 발신자 수, log 스케일 |
| K (키워드) | 0.10 | 정규식. "urgent"=+0.9, "FYI"=−0.4 |
| S (소스·채널) | 0.10 | Slack DM=0.85, Jira blocker=0.90, 이메일 CC=0.35 |

### 4-3. ReAct Tool Registry (긴급도 5 전용)

```python
tools = [
    fetch_email_thread(thread_id),
    fetch_slack_thread(channel, ts),
    fetch_jira_comments(issue_key),
    search_calendar(keyword, date_range),
    get_sender_info(email),
    extract_references(text),
]
# 종료 조건: max 5회 / 추가 참조 없음 / 에이전트 "ENOUGH_CONTEXT" 판단
```

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
    "uvicorn[standard]",      # WebSocket 지원 포함
    # DB
    "tinydb",
    # 스케줄러
    "apscheduler",
    # AI
    "anthropic",              # async 클라이언트 포함
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
# 실행
uv run uvicorn backend.main:app --reload
```

---

## 8. 환경 변수

```bash
# .env

# AI
ANTHROPIC_API_KEY=

# 모델 설정
CLASSIFIER_MODEL=claude-haiku-4-5-20251001
SUMMARIZER_MODEL=claude-sonnet-4-6
ACTION_MODEL=claude-sonnet-4-6
REACT_MODEL=claude-sonnet-4-6

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
FRONTEND_ORIGIN=http://localhost:5173

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

| # | 담당 에이전트 | 브랜치 | 핵심 파일 |
|---|---|---|---|
| 1 | Orchestrator | `feat/orchestrator` | `main.py`, `routers/`, `db/store.py`, `scheduler.py` |
| 2 | Gmail Connector | `feat/gmail-connector` | `connectors/gmail.py`, `routers/auth.py` |
| 3 | Slack + Calendar Connector | `feat/slack-calendar-connector` | `connectors/slack.py`, `connectors/calendar.py` |
| 4 | Urgency Engine | `feat/urgency-engine` | `agents/urgency_engine.py` |
| 5 | Classifier + Summarizer | `feat/classifier-summarizer` | `agents/classifier.py`, `agents/summarizer.py` |
| 6 | Frontend Widget | `feat/briefing-widget` | `frontend/src/` 전체 |

### 브랜치 전략

```
main  ← 배포 가능 상태만. 주 1회 (금요일) dev → main 병합
  └ dev  ← 주간 통합 브랜치. PR 대상
      ├ feat/orchestrator
      ├ feat/gmail-connector
      ├ feat/slack-calendar-connector
      ├ feat/urgency-engine
      ├ feat/classifier-summarizer
      └ feat/briefing-widget
```

### 커밋 컨벤션

```
feat:  새 기능
fix:   버그 수정
chore: 빌드·설정·의존성
docs:  문서
test:  테스트
```

### Week 1 필수 합의 — 인터페이스 스키마 (담당 #1 주도)

프론트엔드(#6)가 mock 데이터로 독립 개발하려면 Week 1 내에 확정해야 한다.  
백엔드 담당(#2~#5)은 이 스키마를 출력 포맷으로 준수한다.

```typescript
// WebSocket으로 스트리밍되는 카드 단위 (분류 완료 즉시 1건씩 전송)
interface WorkCard {
  id: string
  source: "gmail" | "slack" | "calendar"
  summary: string
  urgency_level: 1 | 2 | 3 | 4 | 5
  urgency_breakdown: { T: number; A: number; F: number; K: number; S: number }
  action_type: "reply" | "approve" | "review" | "fyi" | "none"
  from_person: string
  received_at: string        // ISO 8601
  estimated_minutes: number
  due_at: string | null
  status: "pending" | "done" | "snoozed"
}

// 전체 항목 완료 후 1회 전송되는 브리핑 헤더
interface BriefingHeader {
  briefing_id: string
  absence_days: number
  total: number
  urgent: number
  estimated_minutes: number
  contacts_needed: { person: string; reason: string; channel: string }[]
  summary_text: string
}

// WebSocket 메시지 타입 구분
type WSMessage =
  | { type: "card";   data: WorkCard }
  | { type: "header"; data: BriefingHeader }
  | { type: "error";  message: string }
```

### MVP 주차별 체크포인트

| 주차 | 완료 기준 |
|---|---|
| Week 1 | 스키마 확정, Gmail OAuth 로그인 성공, FastAPI `/health` 응답, React 앱 로컬 실행 |
| Week 2 | Gmail 수집 → Urgency Engine 점수 출력 → WebSocket으로 `WorkCard` 1건 전송 확인 |
| Week 3 | Slack·Calendar 포함 전체 파이프라인 E2E, 위젯에 카드 실시간 스트리밍 표시 |
| Week 4 | 체크 완료 인터랙션, 에러 폴백, 브리핑 헤더 표시, 데모 시나리오 통과 |

---

## 10. 주요 설계 결정 (ADR 요약)

| 결정 | 선택 | 대안 | 이유 |
|---|---|---|---|
| 스트리밍 방식 | WebSocket 항목 단위 스트리밍 | 완료 후 일괄 전송 | 60초 로딩 스피너 제거, 긴급 항목 즉시 표시 |
| 긴급도 계산 | 정량 5-신호 엔진 | LLM 판단 | 동일 항목 = 동일 점수 보장, 근거 설명 가능 |
| ReAct 범위 | 긴급도 5 항목만 | 전체 항목 | 비용·시간 최적화, 나머지는 DAG로 충분 |
| DB | TinyDB (JSON) | PostgreSQL | 서버 불필요, MVP 충분. 스키마 동일하게 유지해 추후 마이그레이션 용이 |
| 사내 규정 | 3-레이어 Policy Engine | 프롬프트만 사용 | 규정 위반 보장 (가드레일), 감사 로그, 회사별 설정 파일 분리 |
