from datetime import datetime

from sqlalchemy import select, update, or_, desc, nulls_last
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.db.store import get_session
from backend.db.orm_models import WorkItemORM, ExpenseReportORM


def _row_to_dict(row: WorkItemORM) -> dict:
    return {
        "id":                row.id,
        "user_id":           row.user_id,
        "source":            row.source,
        "raw_content":       row.raw_content,
        "summary":           row.summary,
        "urgency_level":     row.urgency_level,
        "urgency_breakdown": row.urgency_breakdown or {},
        "action_type":       row.action_type,
        "from_person":       row.from_person,
        "due_at":            row.due_at.isoformat() if row.due_at else None,
        "source_id":         row.source_id,
        "status":            row.status,
        "created_at":        row.created_at.isoformat() if row.created_at else None,
        "completed_at":      row.completed_at.isoformat() if row.completed_at else None,
        "actual_minutes":    row.actual_minutes,
        "deadline":          row.deadline.isoformat() if row.deadline else None,
        "urgency_reason":    row.urgency_reason,
    }


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def save_items(items: list[dict]) -> None:
    with get_session() as db:
        for item in items:
            values = dict(
                id                = item["id"],
                user_id           = item.get("user_id", 1),
                source            = item.get("source", ""),
                raw_content       = item.get("raw_content", ""),
                summary           = item.get("summary", ""),
                urgency_level     = item.get("urgency_level", 0),
                urgency_breakdown = item.get("urgency_breakdown", {}),
                urgency_reason    = item.get("urgency_reason"),
                action_type       = item.get("action_type", "none"),
                from_person       = item.get("from_person"),
                due_at            = _parse_dt(item.get("due_at")),
                deadline          = _parse_dt(item.get("deadline")),
                source_id         = item.get("source_id"),
                status            = item.get("status"),
                created_at        = _parse_dt(item.get("created_at")) or datetime.now(),
                completed_at      = _parse_dt(item.get("completed_at")),
                actual_minutes    = item.get("actual_minutes"),
            )
            stmt = pg_insert(WorkItemORM).values(**values).on_conflict_do_update(
                index_elements=["id"],
                set_={k: v for k, v in values.items() if k != "id"},
            )
            db.execute(stmt)


def get_pending_items(user_id: int) -> list[dict]:
    with get_session() as db:
        rows = db.execute(
            select(WorkItemORM).where(WorkItemORM.status == "pending", WorkItemORM.user_id == user_id)
        ).scalars().all()
        return [_row_to_dict(r) for r in rows]


def get_item_by_id(item_id: str, user_id: int) -> dict | None:
    with get_session() as db:
        row = db.execute(
            select(WorkItemORM).where(WorkItemORM.id == item_id, WorkItemORM.user_id == user_id)
        ).scalar_one_or_none()
        return _row_to_dict(row) if row else None


def search_items(user_id: int, query: str = "", status: str = None, source: str = None) -> list[dict]:
    with get_session() as db:
        stmt = select(WorkItemORM).where(WorkItemORM.user_id == user_id)
        if status:
            stmt = stmt.where(WorkItemORM.status == status)
        if source:
            stmt = stmt.where(WorkItemORM.source == source)
        if query:
            q = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    WorkItemORM.summary.ilike(q),
                    WorkItemORM.raw_content.ilike(q),
                )
            )
        stmt = stmt.order_by(nulls_last(desc(WorkItemORM.created_at)))
        rows = db.execute(stmt).scalars().all()
        return [_row_to_dict(r) for r in rows]


def update_item_status(item_id: str, user_id: int, status: str) -> dict:
    with get_session() as db:
        db.execute(
            update(WorkItemORM)
            .where(WorkItemORM.id == item_id, WorkItemORM.user_id == user_id)
            .values(status=status)
        )
    return {"success": True, "item_id": item_id, "status": status}


def save_expense_report(report: dict) -> None:
    with get_session() as db:
        db.add(ExpenseReportORM(
            id           = report["id"],
            user_id      = report.get("user_id", 1),
            created_at   = _parse_dt(report.get("created_at")) or datetime.now(),
            report_type  = report.get("report_type", ""),
            items        = report.get("items", []),
            total_amount = report.get("total_amount", 0),
            xlsx_path    = report.get("xlsx_path"),
            pdf_path     = report.get("pdf_path"),
        ))
