# PostgreSQL 마이그레이션 구현 계획

## 개요

| 항목 | 현재 | 변경 후 |
|---|---|---|
| RDB 저장소 | TinyDB (JSON 파일) | PostgreSQL (RDB) |
| Vector 저장소 | ChromaDB (파일 기반) | PostgreSQL + pgvector |
| 브랜치 | - | `feat/postgresql-migration` |

---

## 마이그레이션 대상

### 1. RDB (TinyDB → PostgreSQL)

#### 직접 수정 파일

| 파일 | 현재 방식 | 변경 내용 |
|---|---|---|
| `backend/db/store.py` | TinyDB 인스턴스 초기화 | SQLAlchemy 엔진 + 세션 초기화로 교체 |
| `backend/tools/storage.py` | TinyDB CRUD 쿼리 | SQL 쿼리 (SQLAlchemy ORM) 로 교체 |
| `backend/config.py` | DB 설정 없음 | `DATABASE_URL` 환경변수 추가 |

#### 간접 영향 파일 (import 구조 유지, 내부 변경 없음)

- `backend/tools/search_items.py`
- `backend/tools/update_status.py`
- `backend/tools/compute_stats.py`
- `backend/tools/write_draft.py`
- `backend/tools/slack_fetch.py`
- `backend/agents/tools_registry.py`

#### 신규 생성 파일

| 파일 | 역할 |
|---|---|
| `backend/db/orm_models.py` | SQLAlchemy ORM 모델 정의 |
| `backend/db/migrations/001_init.sql` | 초기 스키마 SQL |

---

### 2. Vector DB (ChromaDB → pgvector)

#### 직접 수정 파일

| 파일 | 현재 방식 | 변경 내용 |
|---|---|---|
| `backend/tools/policy_search.py` | `langchain_community.Chroma` 검색 | LangChain `PGVector` 백엔드로 교체 |
| `backend/scripts/ingest_policy.py` | `Chroma.from_documents()` 저장 | pgvector 저장으로 교체 |

---

## PostgreSQL 스키마

### RDB 테이블

```sql
-- WorkItem 테이블
CREATE TABLE work_items (
    id                VARCHAR(255) PRIMARY KEY,
    source            VARCHAR(50)  NOT NULL,        -- gmail | slack | calendar | jira | notion
    raw_content       TEXT         NOT NULL,
    summary           TEXT         NOT NULL,
    urgency_level     INT          NOT NULL,
    urgency_breakdown JSONB        NOT NULL DEFAULT '{}',
    action_type       VARCHAR(50)  NOT NULL,         -- reply | approve | review | fyi | none
    from_person       VARCHAR(255),
    due_at            TIMESTAMP,
    source_id         VARCHAR(255),
    status            VARCHAR(50)  NOT NULL DEFAULT 'pending',  -- pending | done | snoozed
    created_at        TIMESTAMP    NOT NULL,
    completed_at      TIMESTAMP,
    actual_minutes    INT
);

CREATE INDEX idx_work_items_status     ON work_items (status);
CREATE INDEX idx_work_items_source     ON work_items (source);
CREATE INDEX idx_work_items_created_at ON work_items (created_at DESC);

-- ExpenseReport 테이블
CREATE TABLE expense_reports (
    id           VARCHAR(255) PRIMARY KEY,
    created_at   TIMESTAMP    NOT NULL,
    report_type  VARCHAR(100) NOT NULL,
    items        JSONB        NOT NULL DEFAULT '[]',
    total_amount INT          NOT NULL,
    xlsx_path    VARCHAR(500),
    pdf_path     VARCHAR(500)
);
```

### Vector DB 테이블 (pgvector)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE policy_embeddings (
    id          VARCHAR(255) PRIMARY KEY,
    content     TEXT    NOT NULL,          -- 자식 청크 텍스트
    parent_text TEXT,                      -- 부모 청크 텍스트
    metadata    JSONB   NOT NULL DEFAULT '{}',
    embedding   vector(1536)               -- text-embedding-3-small 차원
);

CREATE INDEX ON policy_embeddings USING ivfflat (embedding vector_cosine_ops);
```

---

## 데이터 흐름 (변경 후)

```
수집 (Fetch)
  gmail_fetch / slack_fetch / jira_fetch / notion_fetch
        ↓
   WorkItem 생성 (models.py 유지)
        ↓
  storage.save_items()        ← PostgreSQL INSERT
        ↓
  classify / scoring (변경 없음)
        ↓
  storage.search_items()      ← PostgreSQL SELECT
        ↓
  update_status()             ← PostgreSQL UPDATE

문서 검색 (policy_search)
  query → OpenAI Embedding → pgvector similarity search → 결과 반환
```

---

## 의존성 변경

### 제거
```
tinydb
chromadb
langchain-community (Chroma 래퍼 부분)
```

### 추가
```
sqlalchemy
psycopg2-binary
pgvector
langchain-postgres   # LangChain PGVector 백엔드
alembic              # (선택) 마이그레이션 관리
```

---

## 환경변수 추가

```bash
# .env 추가 필요
DATABASE_URL=postgresql://user:password@localhost:5432/whattodo
```

---

## 작업 단계 요약

| 단계 | 내용 | 파일 수 |
|---|---|---|
| 1. 환경 세팅 | PostgreSQL 설치, pgvector 확장, 의존성 교체 | - |
| 2. 스키마 생성 | SQL 테이블 생성, ORM 모델 작성 | 2개 신규 |
| 3. RDB 마이그레이션 | store.py, storage.py 교체 | 2개 수정 |
| 4. Vector DB 마이그레이션 | policy_search.py, ingest_policy.py 교체 | 2개 수정 |
| 5. config 업데이트 | DATABASE_URL 추가 | 1개 수정 |
| 6. 재인게스션 | PDF → pgvector 재임베딩 | 스크립트 실행 |
| 7. 테스트 | 전체 시나리오 eval 재실행 | - |
