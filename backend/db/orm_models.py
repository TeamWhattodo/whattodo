from sqlalchemy import Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class WorkItemORM(Base):
    __tablename__ = "work_items"

    id                = Column(String(255), primary_key=True)
    source            = Column(String(50),  nullable=False)
    raw_content       = Column(Text,        nullable=False)
    summary           = Column(Text,        nullable=False, default="")
    urgency_level     = Column(Integer,     nullable=False, default=0)
    urgency_breakdown = Column(JSON,        nullable=False, default=dict)
    action_type       = Column(String(50),  nullable=False, default="none")
    from_person       = Column(String(255), nullable=True)
    due_at            = Column(DateTime,    nullable=True)
    source_id         = Column(String(255), nullable=True)
    status            = Column(String(50),  nullable=False, default="pending")
    created_at        = Column(DateTime,    nullable=False)
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
