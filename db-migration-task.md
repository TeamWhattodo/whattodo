# DB 마이그레이션 Task 목록 (TinyDB + ChromaDB → PostgreSQL)

> 브랜치: `feat/postgresql-migration`
> 참고: [implementation.md](implementation.md)
> 배포 방식: Docker Compose (앱 + PostgreSQL + pgvector 한번에 실행, 사용자 별도 설치 불필요)

---

## Phase 1. 환경 세팅

- [o] **1-1.** PostgreSQL 로컬 설치 확인 (개발용)
  - 로컬 개발: 설치된 PostgreSQL 사용
  - 배포: Docker Compose로 자동 실행

- [o] **1-2.** `docker-compose.yml` 작성
  - `pgvector/pgvector:pg17` 이미지 (PostgreSQL 17 + pgvector 내장)
  - Python 앱 서비스
  - 볼륨 마운트로 데이터 영속성 확보
  - 환경변수 자동 주입

- [o] **1-3.** `Dockerfile` 작성
  - Python 3.11 기반
  - uv로 의존성 설치
  - Streamlit + FastAPI 실행

- [o] **1-4.** `pyproject.toml` 의존성 교체
  - 제거: `tinydb`, `chromadb`
  - 추가: `sqlalchemy`, `psycopg2-binary`, `pgvector`, `langchain-postgres`
  - 실행: `uv sync`

- [o] **1-5.** `.env` 환경변수 추가
  ```bash
  # 로컬 개발용
  DATABASE_URL=postgresql://postgres:password@localhost:5432/whattodo
  ```

- [o] **1-6.** `backend/config.py` 에 `database_url` 필드 추가

---

## Phase 2. 스키마 및 ORM 모델 생성

- [o] **2-1.** `backend/db/migrations/001_init.sql` 작성
  - `work_items` 테이블 + 인덱스 (status, source, created_at)
  - `expense_reports` 테이블
  - `policy_embeddings` 테이블 (pgvector, embedding vector(1536))
  - IVFFlat 인덱스

- [o] **2-2.** `backend/db/orm_models.py` 작성
  - `Base`, `WorkItemORM`, `ExpenseReportORM` SQLAlchemy 클래스

- [o] **2-3.** 로컬 DB에 스키마 적용 (개발 확인용)
  ```bash
  psql -U postgres -d whattodo -f backend/db/migrations/001_init.sql
  ```

---

## Phase 3. RDB 마이그레이션 (TinyDB → PostgreSQL)

- [o] **3-1.** `backend/db/store.py` 교체
  - TinyDB 제거 → SQLAlchemy `create_engine()`, `sessionmaker()`, `get_session()`

- [o] **3-2.** `backend/tools/storage.py` 함수 교체

  | 함수 | 변경 내용 |
  |---|---|
  | `save_items(items)` | `INSERT ... ON CONFLICT (id) DO NOTHING` |
  | `get_pending_items()` | `SELECT * WHERE status = 'pending'` |
  | `get_item_by_id(id)` | `SELECT * WHERE id = :id` |
  | `search_items(query, status, source)` | `SELECT` + `ILIKE` 조합 |
  | `update_item_status(id, status)` | `UPDATE SET status WHERE id` |
  | `save_expense_report(report)` | `INSERT INTO expense_reports` |

- [o] **3-3.** 동작 확인 (import OK 확인)

---

## Phase 4. Vector DB 마이그레이션 (ChromaDB → pgvector)

- [ ] **4-1.** `backend/scripts/ingest_policy.py` 교체
  - `Chroma.from_documents()` → `PGVector.from_documents()`

- [ ] **4-2.** `backend/tools/policy_search.py` 교체
  - `Chroma` → `PGVector` (LangChain postgres 백엔드)

- [ ] **4-3.** PDF 재인게스션
  ```bash
  uv run python backend/scripts/ingest_policy.py
  ```

- [ ] **4-4.** 동작 확인 (S3 시나리오: "출장비 식대 한도")

---

## Phase 5. 정리 및 검증

- [ ] **5-1.** 구 파일 삭제
  - `backend/db/data/work_items.json`
  - `backend/db/data/expense_reports.json`
  - `backend/db/data/policy_store/`

- [ ] **5-2.** `.gitignore` 정리

- [ ] **5-3.** Docker Compose로 전체 실행 확인
  ```bash
  docker compose up --build
  ```

- [ ] **5-4.** eval 재실행으로 성능 비교
  ```bash
  uv run python -m eval.run_eval
  ```

- [ ] **5-5.** PR 작성 → `dev` 브랜치로 머지

---

## 변경 파일 요약

| 파일 | 작업 | Phase |
|---|---|---|
| `docker-compose.yml` | **신규** Docker 서비스 정의 | 1 |
| `Dockerfile` | **신규** Python 앱 컨테이너 | 1 |
| `pyproject.toml` | 의존성 교체 | 1 |
| `.env` | DATABASE_URL 추가 | 1 |
| `backend/config.py` | database_url 필드 추가 | 1 |
| `backend/db/migrations/001_init.sql` | **신규** 스키마 SQL | 2 |
| `backend/db/orm_models.py` | **신규** ORM 모델 | 2 |
| `backend/db/store.py` | TinyDB → SQLAlchemy | 3 |
| `backend/tools/storage.py` | TinyDB CRUD → SQL | 3 |
| `backend/scripts/ingest_policy.py` | Chroma → PGVector | 4 |
| `backend/tools/policy_search.py` | Chroma → PGVector | 4 |
