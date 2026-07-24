-- WhatToDo 초기 스키마
-- PostgreSQL + pgvector

CREATE EXTENSION IF NOT EXISTS vector;

-- WorkItem 테이블
CREATE TABLE IF NOT EXISTS work_items (
    id                VARCHAR(255) PRIMARY KEY,
    source            VARCHAR(50)  NOT NULL,
    raw_content       TEXT         NOT NULL,
    summary           TEXT         NOT NULL DEFAULT '',
    urgency_level     INT          NOT NULL DEFAULT 0,
    urgency_breakdown JSONB        NOT NULL DEFAULT '{}',
    action_type       VARCHAR(50)  NOT NULL DEFAULT 'none',
    from_person       VARCHAR(255),
    due_at            TIMESTAMP,
    source_id         VARCHAR(255),
    status            VARCHAR(50)  NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMP    NOT NULL,
    completed_at      TIMESTAMP,
    actual_minutes    INT
);

CREATE INDEX IF NOT EXISTS idx_work_items_status     ON work_items (status);
CREATE INDEX IF NOT EXISTS idx_work_items_source     ON work_items (source);
CREATE INDEX IF NOT EXISTS idx_work_items_created_at ON work_items (created_at DESC);

-- ExpenseReport 테이블
CREATE TABLE IF NOT EXISTS expense_reports (
    id           VARCHAR(255) PRIMARY KEY,
    created_at   TIMESTAMP    NOT NULL,
    report_type  VARCHAR(100) NOT NULL,
    items        JSONB        NOT NULL DEFAULT '[]',
    total_amount INT          NOT NULL DEFAULT 0,
    xlsx_path    VARCHAR(500),
    pdf_path     VARCHAR(500)
);

-- 사내 규정 벡터 임베딩 테이블 (pgvector)
CREATE TABLE IF NOT EXISTS policy_embeddings (
    id          VARCHAR(255) PRIMARY KEY,
    content     TEXT         NOT NULL,
    parent_text TEXT,
    metadata    JSONB        NOT NULL DEFAULT '{}',
    embedding   vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_policy_embeddings_ivfflat
    ON policy_embeddings USING ivfflat (embedding vector_cosine_ops);
