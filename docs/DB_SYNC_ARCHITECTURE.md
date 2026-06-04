# WhatToDo — 확장 아키텍처 설계

> 작성 기준일: 2026-06-02  
> 상태: 설계 확정 → 구현 예정

---

## 1. 현재 구조와 한계

### 현재 Supervisor 구조

```
사용자
  │
  ▼
Supervisor (create_react_agent)
  │
  ├── fetch_agent   → 외부 SDK 직접 호출 (Gmail, Slack, Jira, Notion, Calendar)
  ├── report_agent  → 브리핑 포맷 + 파일 생성 (두 역할 혼재)
  ├── search_agent  → TinyDB / ChromaDB 조회
  └── action_agent  → 외부 SDK 쓰기 (발송, 삭제, 생성)

저장소: TinyDB(work_items), JSON 파일(sessions), MemorySaver(LangGraph)
```

### 핵심 문제

| 문제 | 원인 | 체감 영향 |
|---|---|---|
| 응답 지연 5~15초 | 사용자 요청 시점에 외부 API 실시간 호출 | 브리핑 요청마다 매번 대기 |
| LLM 멀티스텝 오류 | LLM이 채널 목록 조회 → 각 채널 fetch를 직접 순서대로 조율 | 잘못된 채널 ID, 누락 채널 발생 |
| 세션 유실 | MemorySaver는 프로세스 재시작 시 이력 소실 | 서버 재시작하면 대화 기억 초기화 |
| 저장소 파편화 | TinyDB, JSON 파일, ChromaDB가 각자 분리 | 데이터 일관성 보장 불가 |
| report_agent 역할 혼재 | 브리핑 포맷과 파일 생성이 같은 에이전트 안에서 처리 | 긴 시스템 프롬프트, 오분류 |

---

## 2. 목표 아키텍처

### 핵심 원칙

> **읽기는 DB에서, 쓰기만 SDK를 직접 호출한다**

외부 API 수집은 백그라운드 워커가 주기적으로 처리하고, 에이전트는 이미 DB에 저장된 데이터만 읽는다.  
사용자 요청과 외부 API 호출이 완전히 분리된다.

### 전체 구조

```
┌──────────────────────────────────────────────────────────────┐
│  백그라운드 워커  (APScheduler — FastAPI lifespan 내장)        │
│                                                              │
│  Gmail ────────────────────────────┐                         │
│  Slack ─────── 주기적 수집 ─────────┤                         │
│  Jira  ─────── (2~15분 간격) ───────┼──→ score_urgency        │
│  Notion ───────────────────────────┤    (정량 긴급도 계산)    │
│  Calendar ─────────────────────────┘         │               │
│                                              ▼               │
│                                        PostgreSQL            │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                  │
│                                                              │
│  work_items   — 수집된 업무 항목 + 긴급도 점수               │
│  sessions     — 대화 이력 (JSON 파일 대체)                    │
│  oauth_tokens — Gmail·Slack 등 소스별 인증 토큰              │
│  sync_log     — 소스별 마지막 싱크 시각·상태                  │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Supervisor (create_react_agent + AsyncPostgresSaver)        │
│                                                              │
│  ├── fetch_agent    → DB SELECT (읽기만)          ~5ms       │
│  ├── briefing_agent → LLM 포맷 변환 (툴 없음)               │
│  ├── report_agent   → 파일 생성 툴 (영수증·KPI)              │
│  ├── search_agent   → DB 쿼리 + ChromaDB 벡터 검색           │
│  └── action_agent   → 외부 SDK 쓰기만 (발송·생성·삭제)       │
└──────────────────────────────────────────────────────────────┘
```

### 지연시간 변화

```
(현재)
사용자 요청 → fetch_agent → 외부 API 다중 호출 → 5~15초 대기 → 응답

(목표)
사용자 요청 → fetch_agent → DB SELECT → <100ms → 응답

백그라운드에서 이미 수집 완료된 상태이므로 요청 시점에 API 호출 없음
```

---

## 3. 서브에이전트 구조 변경

### 역할 분리 기준

| 에이전트 | 출력 대상 | 역할 |
|---|---|---|
| fetch_agent | 내부 | DB에서 업무 항목 읽기 |
| **briefing_agent** | **앱 UI** | **수집 데이터 → 마크다운 시각화** |
| **report_agent** | **외부 파일** | **Excel·PDF 등 파일 export** |
| search_agent | 내부 | DB + ChromaDB 조회 |
| action_agent | 외부 시스템 | SDK 쓰기 (발송·생성·삭제) |

> **핵심 기준**: briefing_agent는 사용자가 앱 안에서 보는 모든 포맷 출력을 담당하고,  
> report_agent는 앱 밖으로 내보내는 파일 생성만 담당한다.

### 현재 → 목표

| 에이전트 | 현재 | 목표 |
|---|---|---|
| fetch_agent | 외부 SDK 직접 호출 | DB SELECT 전용 |
| report_agent | 브리핑 포맷 + 파일 생성 혼재 | **파일 export만** (Excel·PDF) |
| **briefing_agent** | *(없음)* | **신규**: 모든 인앱 마크다운 시각화 |
| search_agent | TinyDB + ChromaDB | DB 쿼리 + ChromaDB (DB만 교체) |
| action_agent | 외부 SDK 쓰기 | 동일 (변경 없음) |

### 서브에이전트별 툴 할당

#### fetch_agent — DB 읽기 전용
```
현재: fetch_gmail, fetch_calendar, fetch_slack_all_items,
      jira_search_issues, notion_search + notion_get_page_content

목표: read_work_items(source, limit, since)   # DB SELECT
      (단일 툴로 전 소스 통합 조회)
```

#### briefing_agent — 툴 없음 (신규)
```
출력 대상: 앱 UI (마크다운 렌더링)
구현: LLM 직접 호출 (create_react_agent 불필요)

담당 범위:
  - 복귀 브리핑      → 긴급도 분류 카드
  - 업무 현황 요약   → 소스별 항목 목록
  - 일정 정리        → 날짜·시간 구조화
  - 검색 결과 정리   → 항목 상세 포맷

출력 형식 (예시):
  ## 📋 업무 브리핑
  ### 🔴 긴급  — 마감 초과 · [긴급] 태그 · High 우선순위
  ### 🟡 중요  — Medium · 답변 필요
  ### 🟢 일반  — 나머지
```

#### report_agent — 외부 파일 export 전용
```
출력 대상: 파일 (Excel .xlsx / PDF)

담당 범위:
  - 정산 리포트   → .xlsx
  - KPI 보고서    → .pdf
  - 영수증 처리   → 정산서 파일

툴: parse_billing_data, parse_receipt_from_text,
    compute_daily_stats, compute_kpi,
    write_report, process_expense_report
```

#### search_agent — DB + 벡터 검색
```
search_past_items   → DB 풀텍스트 검색 (TinyDB → PostgreSQL)
search_company_docs → ChromaDB 벡터 검색 (변경 없음)
get_item_thread     → source_id로 스레드 상세 조회
```

#### action_agent — 외부 SDK 쓰기만 (변경 없음)
```
Gmail:    send_gmail, trash_gmail
Slack:    slack_post_message, slack_delete_message, slack_get_thread_replies
Calendar: create_calendar_block, delete_calendar_block, search_calendar_events
Jira:     jira_create_issue, jira_update_issue, jira_transition_issue,
          jira_delete_issue, jira_add_comment, jira_get_issue, jira_get_transitions
Notion:   notion_create_page, notion_update_page, notion_delete_block,
          list_notion_pages, notion_get_page
기타:     write_draft, update_item_status, search_past_items
```

### Supervisor 라우팅 (목표)

```
업무 현황·브리핑·정리 (앱에서 보기)
  → fetch_agent(request)
  → briefing_agent(context=fetch결과)     ← 마크다운으로 UI 렌더링

파일 export (정산·KPI·영수증)
  → report_agent(request)                ← .xlsx / .pdf 다운로드

특정 항목·규정·스레드 조회
  → search_agent(query)
  → briefing_agent(context=검색결과)     ← 결과도 마크다운으로 정리

답장·발송·일정·Jira·Notion 조작
  → action_agent(request)                ← HitL(사용자 확인) 포함

일반 대화
  → 직접 응답
```

---

## 4. PostgreSQL 스키마

```sql
-- 전 소스 업무 항목 통합
CREATE TABLE work_items (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,         -- gmail | slack | jira | notion | calendar
    raw_content     TEXT,
    summary         TEXT,
    urgency_level   INTEGER DEFAULT 2,     -- score_urgency가 계산해서 채움 (1~5)
    urgency_reason  TEXT,                  -- 긴급도 산정 근거 (예: "마감 2시간 전")
    action_type     TEXT DEFAULT 'none',
    from_person     TEXT,
    source_id       TEXT,                  -- 외부 시스템 원본 ID (threadId 등)
    deadline        TIMESTAMPTZ,           -- 마감 기한 (있는 경우)
    contact_count   INTEGER DEFAULT 1,     -- 동일 발신자 연락 횟수 (누적)
    created_at      TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 대화 세션 (JSON 파일 대체)
CREATE TABLE sessions (
    session_id       TEXT PRIMARY KEY,
    name             TEXT,
    display_messages JSONB DEFAULT '[]',
    history          JSONB DEFAULT '[]',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- OAuth 토큰 (소스별)
CREATE TABLE oauth_tokens (
    source        TEXT PRIMARY KEY,     -- gmail | slack 등
    access_token  TEXT,
    refresh_token TEXT,
    expires_at    TIMESTAMPTZ
);

-- 싱크 상태 로그
CREATE TABLE sync_log (
    source         TEXT PRIMARY KEY,
    last_synced_at TIMESTAMPTZ,
    status         TEXT,                -- success | error | running
    items_count    INTEGER DEFAULT 0,
    error_message  TEXT
);
```

---

## 5. 백그라운드 워커 설계

### APScheduler — FastAPI lifespan 연동

```python
# backend/main.py (예시)
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_gmail,    "interval", minutes=5)
    scheduler.add_job(sync_slack,    "interval", minutes=2)
    scheduler.add_job(sync_jira,     "interval", minutes=10)
    scheduler.add_job(sync_notion,   "interval", minutes=15)
    scheduler.add_job(sync_calendar, "interval", minutes=5)
    scheduler.start()
    yield
    scheduler.shutdown()
```

### 싱크 주기 (제안)

| 소스 | 주기 | 이유 |
|---|---|---|
| Slack | 2분 | 실시간성 중요, rate limit 여유 |
| Gmail | 5분 | push 알림 없음, 폴링 필요 |
| Calendar | 5분 | 일정 변경 빈도 낮음 |
| Jira | 10분 | 이슈 상태 변경 빈도 낮음 |
| Notion | 15분 | 문서 수정 빈도 가장 낮음 |

### score_urgency — 정량 긴급도 계산

수집 직후, DB 저장 전에 실행. LLM 판단 없이 규칙 기반으로 `urgency_level`(1~5)을 계산한다.

| 지표 | 계산 방법 | 최대 기여 |
|---|---|---|
| 마감 임박도 | `deadline`까지 남은 시간 (6h 이내 → +3, 24h 이내 → +2, 48h 이내 → +1) | +3 |
| 발신자 연락 빈도 | 동일 `from_person` 항목 DB COUNT (3회↑ → +2, 2회 → +1) | +2 |
| 미응답 기간 | `(now - created_at)` (48h 초과 → +2, 24h 초과 → +1) | +2 |
| 소스 가중치 | Jira High/Blocker → +2, Gmail → +1, Slack DM → +1 | +2 |
| 키워드 | 제목·본문에 [긴급]/urgent/ASAP → +1 | +1 |

```
총점 → urgency_level
  8+ → 5 (즉시 처리)
  6~7 → 4 (긴급)
  4~5 → 3 (중요)
  2~3 → 2 (일반)
  0~1 → 1 (참고)
```

briefing_agent는 이미 점수가 붙은 항목을 받아 🔴🟡🟢로 분류만 하면 된다.  
"AI 주관 판단이 아닌 정량 지표 기반 우선순위" — 기획 의도가 처음으로 실제 구현된다.

### 워커 동작 원칙

- 이미 저장된 항목(`source_id` 기준)은 중복 저장하지 않고 갱신
- 신규 항목에는 `score_urgency` 실행 후 저장, 기존 항목은 주기적으로 점수 재계산 (마감 임박 반영)
- 싱크 실패 시 `sync_log`에 기록하고 다음 주기에 재시도
- action_agent가 발송한 내용도 즉시 `work_items`에 기록 (중복 방지)

---

## 6. Docker Compose 구성

### 서비스 구조

세 컨테이너를 하나의 `docker-compose.yml`로 묶어 띄운다.

```
Docker 내부 네트워크
  frontend (nginx)  ←→  backend (FastAPI)  ←→  db (PostgreSQL)
  :80                    :8000                   :5432

호스트(브라우저) 접근
  http://localhost     → React 앱
  http://localhost:8000 → API (프론트가 내부에서 참조)
  DB는 외부 노출 없음 (컨테이너 간 내부 통신만)
```

### docker-compose.yml (예시)

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: whattodo
      POSTGRES_USER: whattodo
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    # 포트 노출 없음 — backend와 내부 네트워크로만 통신

  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://whattodo:secret@db:5432/whattodo
    env_file:
      - .env                        # API 키 등 민감 정보
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "80:80"                     # http://localhost 로 접속
    depends_on:
      - backend

volumes:
  pgdata:
```

### frontend Dockerfile (프로덕션 빌드)

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build          # Vite → dist/

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # React SPA — 모든 경로를 index.html로
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 요청은 backend 컨테이너로 프록시
    location /api/ {
        proxy_pass http://backend:8000;
    }
}
```

> nginx가 `/api/` 프록시를 처리하므로, React 코드의 API URL을 `/api`로 변경하면  
> 개발(`localhost:8000`)과 프로덕션(`localhost`) 환경을 `.env`로 분리할 수 있다.

### 실행

```bash
docker compose up --build      # 최초 빌드 포함 실행
docker compose up -d           # 백그라운드 실행
docker compose down            # 종료
docker compose logs -f backend # 로그 확인
```

접속: **`http://localhost`** — 브라우저에서 바로 접근 가능.

---

## 8. LangGraph 체크포인터 교체

```python
# 현재
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()          # 프로세스 재시작 시 유실

# 목표
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
checkpointer = AsyncPostgresSaver(conn)  # PostgreSQL에 영구 저장
```

세션 파일 기반 복원 로직(`_build_messages`, `load_session`) 제거 가능.

---

## 9. 구현 단계

### Phase 1 — 저장소 통합
- [ ] Docker Compose: Frontend + Backend + PostgreSQL 구성 (섹션 6 참고)
- [ ] PostgreSQL 스키마 생성 (위 4개 테이블)
- [ ] 기존 TinyDB → PostgreSQL `work_items` 마이그레이션
- [ ] 기존 JSON 파일 세션 → PostgreSQL `sessions` 마이그레이션
- [ ] LangGraph MemorySaver → `AsyncPostgresSaver` 교체

### Phase 2 — 백그라운드 워커
- [ ] APScheduler FastAPI lifespan 연동
- [ ] 소스별 싱크 워커 구현 (Gmail, Slack, Jira, Notion, Calendar)
- [ ] `score_urgency` 로직 구현 (수집 후 자동 실행)
- [ ] OAuth 토큰 DB 저장 + 만료 시 자동 갱신
- [ ] `/api/sync/status` 엔드포인트 (마지막 싱크 시각 확인용)

### Phase 3 — 에이전트 DB 연동
- [ ] fetch_agent: 외부 API 호출 → `read_work_items` DB 툴로 전환
- [ ] search_agent: TinyDB → PostgreSQL 쿼리로 전환
- [ ] briefing_agent 신규 구현 (report_agent에서 분리)
- [ ] report_agent: 브리핑 로직 제거, 파일 생성만 유지
- [ ] 강제 새로고침 옵션 (`fetch_agent`에 `force_sync=True` 파라미터)

---

## 10. 리스크 및 고려사항

| 항목 | 내용 |
|---|---|
| 데이터 신선도 | 싱크 주기만큼 최신 데이터가 아닐 수 있음. 긴급 알림은 웹훅으로 보완 가능 (Slack Events API 등) |
| OAuth 토큰 갱신 | Gmail refresh_token 만료 시 재인증 흐름 필요. 프론트에 재인증 유도 UI 필요 |
| 쓰기 일관성 | action_agent 발송 후 즉시 DB 반영해야 중복 발송 방지 가능 |
| 멀티유저 | 현재는 단일 사용자 가정. 멀티유저로 확장 시 `user_id` 컬럼 추가 필요 |

---

## 11. 미결 사항 (팀 논의)

- [ ] Notion 통합 수집 툴(`fetch_notion_all`) 추가 여부
- [ ] 실시간 웹훅 적용 범위 (Slack Events API, Gmail Push Notification)
- [ ] 싱크 주기 최종 확정
- [ ] 사용자별 멀티테넌시 지원 시점
