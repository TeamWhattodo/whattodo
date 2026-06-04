from backend.workers.base import run_sync
from backend.tools.calendar_fetch import fetch_calendar


def _fetch(user_id: int) -> list[dict]:
    items = fetch_calendar(user_id=user_id, days=14)
    return [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]


def sync_calendar():
    from backend.db.store import get_session
    from backend.db.orm_models import IntegrationCredentialORM
    from sqlalchemy import select
    
    with get_session() as db:
        users = db.execute(select(IntegrationCredentialORM.user_id).where(IntegrationCredentialORM.source == "google")).scalars().all()
        for uid in users:
            run_sync("calendar", _fetch, user_id=uid)
