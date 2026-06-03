"""업무 목록 조회 — work_items 테이블에서 기간별 조회."""
from datetime import datetime, timezone


def fetch_tasks(start: str, end: str) -> dict:
    """지정 기간의 완료 업무 목록을 DB에서 가져온다.
    start/end: YYYY-MM-DD 형식.
    status='done'이고 completed_at이 해당 기간에 속하는 항목을 반환.
    """
    from backend.db.store import SessionLocal
    from backend.db.orm_models import WorkItemORM
    from sqlalchemy import and_

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt   = datetime.fromisoformat(end).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    with SessionLocal() as session:
        rows = (
            session.query(WorkItemORM)
            .filter(
                and_(
                    WorkItemORM.status == "done",
                    WorkItemORM.completed_at >= start_dt,
                    WorkItemORM.completed_at <= end_dt,
                )
            )
            .order_by(WorkItemORM.completed_at.asc())
            .all()
        )

        tasks = [
            {
                "id":          row.id,
                "title":       row.summary or row.raw_content[:100],
                "source":      row.source,
                "category":    row.action_type,
                "date":        row.completed_at.strftime("%Y-%m-%d") if row.completed_at else None,
                "assignee":    row.from_person or "-",
                "description": row.raw_content[:200] if row.raw_content else "",
            }
            for row in rows
        ]

    return {
        "period": {"start": start, "end": end},
        "tasks":  tasks,
        "total":  len(tasks),
    }
