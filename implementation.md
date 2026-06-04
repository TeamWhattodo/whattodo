# WhatToDo — DB 통합 및 확장 아키텍처 구현 계획

> 참고 문서: [docs/DB_SYNC_ARCHITECTURE.md](docs/DB_SYNC_ARCHITECTURE.md)  
> 브랜치: `feat/postgresql-migration`

---

## 핵심 원칙

> **읽기는 DB에서, 쓰기만 SDK를 직접 호출한다**

외부 API 수집은 백그라운드 워커가 주기적으로 처리.  
에이전트는 DB에 저장된 데이터만 읽어 응답 → 요청 시점 외부 API 호출 제거.

---

## 전체 구조 (목표)

```
┌─────────────────────────────────────────────────────┐
│  백그라운드 워커 (APScheduler)                        │
│  Gmail(5분) / Slack(2분) / Jira(10분) /              │
│  Notion(15분) / Calendar(5분)                        │
│         ↓ score_urgency 계산 후 저장                  │
│              PostgreSQL                              │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│  Supervisor (AsyncPostgresSaver)                    │
│  ├── fetch_agent    → DB SELECT 전용 (~5ms)         │
│  ├── briefing_agent → 마크다운 시각화 (신규)         │
│  ├── report_agent   → 파일 export 전용              │
│  ├── search_agent   → DB + pgvector 검색            │
│  └── action_agent   → 외부 SDK 쓰기만               │
└─────────────────────────────────────────────────────┘
```

---

## 현재 완료 현황

| 항목 | 상태 |
|---|---|
| PostgreSQL 로컬 세팅 + docker-compose.dev.yml | ✅ |
| pyproject.toml 의존성 교체 (tinydb/chromadb 제거) | ✅ |
| ORM 모델 (WorkItemORM, ExpenseReportORM) | ✅ |
| store.py SQLAlchemy 교체 + init_db() | ✅ |
| storage.py TinyDB → SQL upsert | ✅ |
| fetch_agent Jira/Notion MCP 저장 래퍼 | ✅ |
| Gmail query 파라미터 동적 조회 | ✅ |

---

## PostgreSQL 스키마 (최종)

```sql
-- 업무 항목 (현재 구현됨 + 컬럼 추가 예정)
CREATE TABLE work_items (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    raw_content     TEXT,
    summary         TEXT,
    urgency_level   INTEGER DEFAULT 2,
    urgency_reason  TEXT,
    action_type     TEXT DEFAULT 'none',
    from_person     TEXT,
    source_id       TEXT,
    deadline        TIMESTAMPTZ,
    contact_count   INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ,
    synced_at       TIMESTAMPTZ DEFAULT NOW(),
    status          TEXT DEFAULT 'pending'
);

-- 대화 세션 (JSON 파일 → DB 이관 예정)
CREATE TABLE sessions (
    session_id       TEXT PRIMARY KEY,
    name             TEXT,
    display_messages JSONB DEFAULT '[]',
    history          JSONB DEFAULT '[]',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 사용자 계정 (신규)
CREATE TABLE users (
    id             SERIAL PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    access_token   TEXT,
    refresh_token  TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- OAuth 토큰 (다중 사용자 및 암호화 지원)
CREATE TABLE oauth_tokens (
    user_id       INTEGER REFERENCES users(id),
    source        TEXT,
    access_token  TEXT,
    refresh_token TEXT,
    expires_at    TIMESTAMPTZ,
    PRIMARY KEY (user_id, source)
);

-- 싱크 상태 로그 (신규)
CREATE TABLE sync_log (
    source         TEXT PRIMARY KEY,
    last_synced_at TIMESTAMPTZ,
    status         TEXT,
    items_count    INTEGER DEFAULT 0,
    error_message  TEXT
);

-- 사내 규정 벡터 임베딩 (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE policy_embeddings (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    parent_text TEXT,
    metadata    JSONB DEFAULT '{}',
    embedding   vector(1536)
);
```

---

## 에이전트 구조 변경

| 에이전트 | 현재 | 목표 |
|---|---|---|
| fetch_agent | 외부 SDK 직접 호출 | DB SELECT 전용 |
| briefing_agent | *(없음)* | **신규** — 인앱 마크다운 시각화 |
| report_agent | 브리핑 포맷 + 파일 생성 혼재 | 파일 export 전용 |
| search_agent | TinyDB + ChromaDB | PostgreSQL + pgvector |
| action_agent | 외부 SDK 쓰기 | 변경 없음 |

---

## Docker Compose 최종 구성

```
frontend (nginx:80) ←→ backend (FastAPI:8000) ←→ db (PostgreSQL:5432)
```

- frontend: React Vite 빌드 → nginx 서빙, `/api/` 요청은 backend로 프록시
- backend: FastAPI + APScheduler 백그라운드 워커
- db: pgvector/pgvector:pg17

---

## 의존성 추가 예정

```
apscheduler          # 백그라운드 워커
langgraph-checkpoint-postgres  # AsyncPostgresSaver
cryptography         # 토큰 암/복호화 (Fernet)
```

---

## 인증 및 보안 플로우 (JWT & OAuth)

1. **앱 자체 로그인 (`/login`)**
   - 액세스 토큰 및 리프레시 토큰(만료기간 김) 발급.
   - 발급된 토큰들은 브라우저 `HttpOnly Cookie`에 저장되며, DB `users` 테이블에도 저장되어 세션 관리.
2. **토큰 갱신 로직 (`/refresh`)**
   - 액세스 토큰 만료로 인한 401 발생 시, 프론트엔드가 `/refresh` 호출.
   - 쿠키에 있는 리프레시 토큰을 읽어 DB의 값과 대조 후 새 액세스 토큰 발급.
   - 리프레시 토큰마저 만료된 경우 재로그인(ID/PW 입력) 화면으로 강제 이동.
3. **외부 연동 토큰 암호화**
   - `.env`에 등록된 `OAUTH_ENCRYPTION_KEY`를 이용해 `oauth_tokens` 테이블에 저장 시 양방향 암호화 적용.
   - 프론트엔드로는 토큰 값이 아닌 연동 여부(`status: connected`) 상태만 전달.
   - 백엔드 내부 로직 동작 시에만 실시간 복호화하여 사용.
