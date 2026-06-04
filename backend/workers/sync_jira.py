import json
from datetime import datetime
from backend.workers.base import run_sync
from backend.tools.jira_fetch import jira_search_issues


def _fetch(user_id: int, days: int = 14) -> list[dict]:
    # Pass user_id directly to _client or tools, but tools require RunnableConfig.
    # We can craft a mock config or directly call the underlying fetch logic.
    # The simplest way is to call _client directly:
    from backend.tools.jira_fetch import _client
    
    client = _client(user_id=user_id)
    jql = f"statusCategory not in (Done) AND updated >= -{days}d ORDER BY updated DESC"
    raw = client.search_issues(
        jql,
        maxResults=50,
        fields="summary,status,assignee,priority,created,updated,description",
    )
    
    items = []
    for issue in raw:
        items.append({
            "id": f"jira_{issue.key}",
            "user_id": user_id,
            "source": "jira",
            "source_id": issue.key,
            "raw_content": json.dumps({
                "key": issue.key,
                "summary": issue.fields.summary,
                "status": issue.fields.status.name,
            }, ensure_ascii=False, default=str),
            "summary": issue.fields.summary,
            "action_type": "review",
            "from_person": issue.fields.assignee.displayName if issue.fields.assignee else None,
            "due_at": getattr(issue.fields, "duedate", None),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        })
    return items

def sync_jira():
    from backend.db.store import get_session
    from backend.db.orm_models import IntegrationCredentialORM
    from backend.auth.models import User
    from sqlalchemy import select
    
    with get_session() as db:
        stmt = (
            select(IntegrationCredentialORM.user_id, User.sync_settings)
            .join(User, User.id == IntegrationCredentialORM.user_id)
            .where(IntegrationCredentialORM.source == "jira")
        )
        users = db.execute(stmt).all()
        for uid, settings in users:
            days = (settings or {}).get("jira", 14)
            run_sync(f"jira_{uid}", _fetch, user_id=uid, days=days)
