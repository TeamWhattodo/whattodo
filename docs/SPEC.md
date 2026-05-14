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
│   ├── main.py                  # FastAPI 앱 (OAuth 콜백 + health)
│   ├── routers/
│   │   └── auth.py              # OAuth 콜백 수신 (MVP 유일한 라우터)
│   │   # briefing.py 등 Widget Phase에서 추가
│   ├── agents/
│   │   ├── orchestrator.py      # 전체 파이프라인 제어
│   │   ├── llm_client.py        # LLM Provider 추상화 (Fast/Smart 티어)
│   │   ├── urgency_engine.py    # 정량 5-신호 계산 (LLM 없음)
│   │   ├── classifier.py        # Fast 티어: 액션 타입 + 요약
│   │   ├── react_agent.py       # Smart 티어: 긴급도 5 전용 ReAct 루프
│   │   └── summarizer.py        # Smart 티어: 브리핑 헤더 생성
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
│   ├── models.py                # 공유 Pydantic 모델 (WorkCard, BriefingHeader 등)
│   ├── scheduler.py             # APScheduler 크론 등록
│   └── config.py                # pydantic-settings 환경 변수
├── app.py                       # Streamlit 앱 (UI 진입점)
├── pages/
│   ├── briefing.py              # 복귀 브리핑 화면
│   ├── daily_summary.py         # 일간 결산 화면
│   └── kpi_report.py            # KPI 리포트 화면
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

| 컴포넌트 | 모델 티어 | 역할 | LLM 사용 여부 |
|---|---|---|---|
| Urgency Engine | — | 정량 5-신호 긴급도 계산 | ❌ 순수 Python |
| Classifier | **Fast** (저비용·고속) | 액션 타입 분류 + 1~2줄 요약 | ✅ (~200 토큰/항목) |
| ReAct Agent | **Smart** (고성능) | 긴급도 5 항목 교차 참조 수집 | ✅ (최대 5회 반복) |
| Summarizer | **Smart** (고성능) | 브리핑 헤더·통계 문구 생성 | ✅ (전체 완료 후 1회) |
| Action Agent | **Smart** (고성능) | 답장 초안 생성 | ✅ (on-demand) |
| Daily Narrative | **Fast** (저비용·고속) | 일간 결산 코멘트 (~300 토큰) | ✅ |
| KPI Narrative | **Smart** (고성능) | 주간 KPI 분석 코멘트 (~500 토큰) | ✅ |

> 모델 티어는 환경 변수로 실제 모델명에 매핑됩니다. 코드는 티어 이름만 참조합니다. (→ 4-4 참고)

### 4-2. Urgency Engine 공식

```
urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S
urgency_level = ceil(urgency_score × 5)   →  1~5
```

| 신호 | 가중치 | 측정 방법 |
|---|---|---|
| T (마감 잔여 시간) | 0.35 | 지수 감쇠. 초과=1.0, 24h 후=0.12, 없음=최대 0.6 |
| A (발신자 중요도) | 0.25 | 아래 별도 설명 — **구현 방법 미확정** |
| F (반복 추적) | 0.20 | 미응답 동일 발신자 수, log 스케일 |
| K (키워드) | 0.10 | 정규식. "urgent"=+0.9, "FYI"=−0.4 |
| S (소스·채널) | 0.10 | Slack DM=0.85, Jira blocker=0.90, 이메일 CC=0.35 |

#### A 신호 — 발신자 중요도 취득 방법 (미확정)

사내 DB가 없는 개인 툴 특성상, 조직도를 직접 연동할 수 없다.  
아래 3가지 방법을 우선순위 순으로 조합하는 방향을 검토 중이나 **최종 구현 방법은 미확정**.

| 우선순위 | 방법 | 특징 |
|---|---|---|
| 1 | **온보딩 태깅** | 연동 직후 자주 연락하는 상위 10명을 4단계(임원·팀장·동료·기타)로 태깅. 30초 내 완료. 가장 정확. |
| 2 | **이메일 서명 파싱** | 서명에서 "대표", "CEO", "팀장" 등 직함 키워드 감지. 무설정 자동. |
| 3 | **행동 기반 추정** | 과거 평균 응답 시간·내가 먼저 연락한 비율·메시지 빈도로 중요도 추정. 데이터 축적 후 정확도 향상. |
| — | **기본값** | 위 3가지 모두 해당 없으면 0.4 (unknown) |

```python
# 우선순위 조합 (구현 예시 — 미확정)
def get_authority_score(sender, user_settings, history) -> float:
    if score := user_settings.tagged.get(sender.email):
        return score                                    # 1순위: 온보딩 태깅
    if score := parse_title_from_signature(sender):
        return score                                    # 2순위: 서명 파싱
    if history.has_enough_data(sender.email):
        return behavioral_score(sender.email, history) # 3순위: 행동 추정
    return 0.4                                         # 기본값
```

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

### 4-4. LLM Provider 추상화

에이전트 코드는 어떤 SDK를 쓰는지 몰라도 됩니다. `LLMClient`만 호출하면 환경 변수에 따라 Anthropic 또는 OpenAI로 라우팅됩니다.

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
agents/classifier.py
agents/summarizer.py      →  agents/llm_client.py  →  anthropic SDK
agents/react_agent.py                               →  openai SDK
agents/action_agent.py
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

| # | 담당 에이전트 | 브랜치 | 핵심 파일 |
|---|---|---|---|
| 1 | Orchestrator | `feat/orchestrator` | `main.py`, `routers/auth.py`, `models.py`, `db/store.py`, `scheduler.py` |
| 2 | Gmail Connector | `feat/gmail-connector` | `connectors/gmail.py`, `routers/auth.py` |
| 3 | Slack + Calendar Connector | `feat/slack-calendar-connector` | `connectors/slack.py`, `connectors/calendar.py` |
| 4 | Urgency Engine | `feat/urgency-engine` | `agents/urgency_engine.py` |
| 5 | Classifier + Summarizer | `feat/classifier-summarizer` | `agents/classifier.py`, `agents/summarizer.py` |
| 6 | Streamlit UI | `feat/streamlit-ui` | `app.py`, `pages/` 전체 |

### 브랜치 전략

```
main  ← 배포 가능 상태만. 주 1회 (금요일) dev → main 병합
  └ dev  ← 주간 통합 브랜치. PR 대상
      ├ feat/orchestrator
      ├ feat/gmail-connector
      ├ feat/slack-calendar-connector
      ├ feat/urgency-engine
      ├ feat/classifier-summarizer
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
| 긴급도 계산 | 정량 5-신호 엔진 | LLM 판단 | 동일 항목 = 동일 점수 보장, 근거 설명 가능 |
| ReAct 범위 | 긴급도 5 항목만 | 전체 항목 | 비용·시간 최적화, 나머지는 DAG로 충분 |
| DB | TinyDB (JSON) | PostgreSQL | 서버 불필요, MVP 충분. 스키마 동일하게 유지해 추후 마이그레이션 용이 |
| 사내 규정 | 3-레이어 Policy Engine | 프롬프트만 사용 | 규정 위반 보장 (가드레일), 감사 로그, 회사별 설정 파일 분리 |
| LLM Provider | 추상화 래퍼 (Fast/Smart 티어) | SDK 직접 호출 | Anthropic ↔ OpenAI 교체 시 llm_client.py 1개 파일만 수정 |
