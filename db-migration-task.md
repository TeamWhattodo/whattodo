# DB 마이그레이션 Task 목록

> 브랜치: `feat/postgresql-migration`  
> 참고: [implementation.md](implementation.md) | [docs/DB_SYNC_ARCHITECTURE.md](docs/DB_SYNC_ARCHITECTURE.md)  
> 배포 방식: Docker Compose (frontend + backend + PostgreSQL)

---

## Phase 1. 환경 세팅 ✅ 완료

- [o] **1-1.** PostgreSQL 로컬 설치 확인
- [o] **1-2.** `docker-compose.dev.yml` 작성 (DB 단독 개발용)
- [o] **1-3.** `Dockerfile` 작성 (Python 앱)
- [o] **1-4.** `pyproject.toml` 의존성 교체 (tinydb/chromadb 제거, sqlalchemy 등 추가)
- [o] **1-5.** `.env` DATABASE_URL 추가
- [o] **1-6.** `backend/config.py` database_url 필드 추가

---

## Phase 2. 스키마 및 ORM 모델 ✅ 완료

- [o] **2-1.** `backend/db/migrations/001_init.sql` 작성
- [o] **2-2.** `backend/db/orm_models.py` 작성 (WorkItemORM, ExpenseReportORM)
- [o] **2-3.** 로컬 DB 스키마 적용

---

## Phase 3. RDB 마이그레이션 (TinyDB → PostgreSQL) ✅ 완료

- [o] **3-1.** `backend/db/store.py` SQLAlchemy로 교체
- [o] **3-2.** `backend/tools/storage.py` upsert SQL로 교체
- [o] **3-3.** `backend/main.py` init_db() 추가
- [o] **3-4.** Jira/Notion MCP 결과 WorkItem 변환 래퍼 추가 (fetch_agent)
- [o] **3-5.** fetch_calendar save_items 추가

---

## Phase 4. 스키마 확장 (신규 테이블)

- [ ] **4-1.** `sessions` 테이블 추가 (JSON 파일 세션 → DB 이관)
  ```sql
  CREATE TABLE sessions (session_id, name, display_messages, history, created_at, updated_at)
  ```
- [ ] **4-2.** `sync_log` 테이블 추가 (소스별 마지막 싱크 시각·상태)
  ```sql
  CREATE TABLE sync_log (source, last_synced_at, status, items_count, error_message)
  ```
- [ ] **4-3.** `oauth_tokens` 테이블 추가 (토큰 파일 → DB 이관)
  ```sql
  CREATE TABLE oauth_tokens (source, access_token, refresh_token, expires_at)
  ```
- [ ] **4-4.** `work_items` 컬럼 보완 (`urgency_reason`, `deadline`, `contact_count`, `synced_at`)
- [ ] **4-5.** `backend/db/migrations/002_extend.sql` 작성 및 적용
- [ ] **4-6.** ORM 모델 업데이트

---

## Phase 5. 백그라운드 워커 (APScheduler)

- [o] **5-1.** `apscheduler` 의존성 추가
- [o] **5-2.** `backend/workers/` 디렉토리 생성
- [o] **5-3.** 소스별 싱크 워커 구현
  - `sync_gmail.py` — 5분 주기
  - `sync_slack.py` — 2분 주기
  - `sync_jira.py` — 10분 주기
  - `sync_notion.py` — 15분 주기
  - `sync_calendar.py` — 5분 주기
- [-] **5-4.** `score_urgency` 로직 구현 — 미구현 (제외)
- [o] **5-5.** `backend/main.py` lifespan에 APScheduler 연동 (서버 시작 시 즉시 실행)
- [o] **5-6.** `sync_log` 기록 + 실패 시 재시도 로직
- [o] **5-7.** `/api/sync/status` 엔드포인트 추가

---

## Phase 6. 에이전트 구조 개편

- [o] **6-1.** `fetch_agent` — 외부 API 호출 제거, `read_work_items` DB 툴로 전환
- [o] **6-2.** `briefing_agent` 신규 구현 (Python 포맷 + Supervisor LLM 자연어 응답)
- [o] **6-3.** `report_agent` 리팩토링 — 파일 export 전용 (브리핑 로직 제거)
- [o] **6-4.** Supervisor 라우팅 업데이트 (briefing_agent 연결)

---

## Phase 7. Vector DB 마이그레이션 (ChromaDB → pgvector)

- [ ] **7-1.** `backend/scripts/ingest_policy.py` — `PGVector.from_documents()`로 교체
- [ ] **7-2.** `backend/tools/policy_search.py` — `PGVector` 백엔드로 교체
- [ ] **7-3.** PDF 재인게스션 실행
- [ ] **7-4.** 동작 확인 (S3 시나리오: "출장비 식대 한도")

---

## Phase 8. LangGraph 체크포인터 교체

- [ ] **8-1.** `langgraph-checkpoint-postgres` 의존성 추가
- [ ] **8-2.** `MemorySaver` → `AsyncPostgresSaver` 교체
- [ ] **8-3.** 세션 파일 복원 로직 제거 (`_build_messages`, `load_session`)

---

## Phase 9. Docker Compose 최종 구성

- [ ] **9-1.** `frontend/Dockerfile` 작성 (Vite 빌드 → nginx)
- [ ] **9-2.** `frontend/nginx.conf` 작성 (`/api/` 프록시 설정)
- [ ] **9-3.** `docker-compose.yml` 업데이트 (frontend 서비스 추가)
- [ ] **9-4.** `App.jsx` API URL → `/api`로 변경 (nginx 프록시 활용)
- [ ] **9-5.** `docker compose up --build` 전체 실행 확인

---

## Phase 10. 검증

- [ ] **10-1.** 구 파일 삭제 (`work_items.json`, `expense_reports.json`, `policy_store/`)
- [ ] **10-2.** eval 재실행 및 마이그레이션 전 결과와 비교
- [ ] **10-3.** PR 작성 → `dev` 브랜치 머지

---

## 변경 파일 요약

| 파일 | 작업 | Phase |
|---|---|---|
| `docker-compose.dev.yml` | 개발용 DB 단독 | 1 ✅ |
| `Dockerfile` | Python 앱 | 1 ✅ |
| `pyproject.toml` | 의존성 교체 | 1 ✅ |
| `.env` / `config.py` | DATABASE_URL | 1 ✅ |
| `backend/db/orm_models.py` | ORM 모델 | 2 ✅ |
| `backend/db/store.py` | SQLAlchemy | 2-3 ✅ |
| `backend/tools/storage.py` | upsert SQL | 3 ✅ |
| `backend/db/migrations/002_extend.sql` | 신규 테이블 | 4 |
| `backend/workers/sync_*.py` | 백그라운드 워커 | 5 |
| `backend/agents/subagents/fetch_agent.py` | DB 전용 | 6 |
| `backend/agents/subagents/briefing_agent.py` | 신규 | 6 |
| `backend/agents/subagents/report_agent.py` | 파일 export만 | 6 |
| `backend/tools/policy_search.py` | pgvector | 7 |
| `backend/scripts/ingest_policy.py` | pgvector | 7 |
| `backend/agents/graph.py` | AsyncPostgresSaver | 8 |
| `frontend/Dockerfile` | nginx 빌드 | 9 |
| `frontend/nginx.conf` | 프록시 설정 | 9 |
| `docker-compose.yml` | frontend 추가 | 9 |
