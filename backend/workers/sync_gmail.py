from backend.workers.base import run_sync
from backend.tools.gmail_fetch import fetch_gmail


def _fetch(user_id: int, days: int = 14) -> list[dict]:
    query = f"newer_than:{days}d"
    items = fetch_gmail(user_id=user_id, max_results=50, query=query)
    return [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]


def sync_gmail():
    from backend.db.store import get_session
    from backend.db.orm_models import IntegrationCredentialORM
    from backend.auth.models import User
    from sqlalchemy import select
    
    with get_session() as db:
        stmt = (
            select(IntegrationCredentialORM.user_id, User.sync_settings)
            .join(User, User.id == IntegrationCredentialORM.user_id)
            .where(IntegrationCredentialORM.source == "google")
        )
        users = db.execute(stmt).all()
        for uid, settings in users:
            days = (settings or {}).get("gmail", 14)
            run_sync("gmail", _fetch, user_id=uid, days=days)
