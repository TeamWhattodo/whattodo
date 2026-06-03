from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, func
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class WorkItemORM(Base):
    __tablename__ = "work_items"

    id                = Column(String(255), primary_key=True)
    source            = Column(String(50),  nullable=False)
    raw_content       = Column(Text,        nullable=True,  default="")
    summary           = Column(Text,        nullable=True,  default="")
    urgency_level     = Column(Integer,     nullable=False, default=2)
    urgency_reason    = Column(Text,        nullable=True)
    urgency_breakdown = Column(JSON,        nullable=True,  default=dict)
    action_type       = Column(String(50),  nullable=False, default="none")
    from_person       = Column(String(255), nullable=True)
    due_at            = Column(DateTime,    nullable=True)
    deadline          = Column(TIMESTAMPTZ, nullable=True)
    source_id         = Column(String(255), nullable=True)
    contact_count     = Column(Integer,     nullable=False, default=1)
    status            = Column(String(50),  nullable=False, default="pending")
    created_at        = Column(DateTime,    nullable=True)
    synced_at         = Column(TIMESTAMPTZ, nullable=True,  server_default=func.now())
    completed_at      = Column(DateTime,    nullable=True)
    actual_minutes    = Column(Integer,     nullable=True)


class ExpenseReportORM(Base):
    __tablename__ = "expense_reports"

    id           = Column(String(255), primary_key=True)
    created_at   = Column(DateTime,    nullable=False)
    report_type  = Column(String(100), nullable=False)
    items        = Column(JSON,        nullable=False, default=list)
    total_amount = Column(Integer,     nullable=False, default=0)
    xlsx_path    = Column(String(500), nullable=True)
    pdf_path     = Column(String(500), nullable=True)


class SessionORM(Base):
    __tablename__ = "sessions"

    session_id       = Column(String(255), primary_key=True)
    name             = Column(String(255), nullable=True)
    display_messages = Column(JSONB,       nullable=False, default=list)
    history          = Column(JSONB,       nullable=False, default=list)
    created_at       = Column(TIMESTAMPTZ, nullable=False, server_default=func.now())
    updated_at       = Column(TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now())


class SyncLogORM(Base):
    __tablename__ = "sync_log"

    source         = Column(String(50),  primary_key=True)
    last_synced_at = Column(TIMESTAMPTZ, nullable=True)
    status         = Column(String(20),  nullable=False, default="idle")
    items_count    = Column(Integer,     nullable=False, default=0)
    error_message  = Column(Text,        nullable=True)


class OAuthTokenORM(Base):
    __tablename__ = "oauth_tokens"

    source        = Column(String(50),  primary_key=True)
    access_token  = Column(Text,        nullable=True)
    refresh_token = Column(Text,        nullable=True)
    expires_at    = Column(TIMESTAMPTZ, nullable=True)
