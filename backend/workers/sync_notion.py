import json
from datetime import datetime
from backend.workers.base import run_sync


def _fetch(user_id: int, days: int = 14) -> list[dict]:
    try:
        from backend.tools.notion_fetch import _client
        from datetime import datetime, timedelta, timezone
        client = _client(user_id=user_id)
        response = client.search(
            query="",
            sort={"direction": "descending", "timestamp": "last_edited_time"},
            page_size=50
        )
        pages = response.get("results", [])
    except Exception:
        return []

    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    for page in pages:
        edited_time = page.get("last_edited_time")
        if edited_time:
            try:
                page_time = datetime.fromisoformat(edited_time.replace("Z", "+00:00"))
                if page_time < cutoff:
                    continue
            except ValueError:
                pass
                
        page_id = page.get("id", "")
        title = ""
        for prop in page.get("properties", {}).values():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_items = prop.get("title", [])
                if title_items:
                    title = title_items[0].get("plain_text", "")
                    break
        if not title:
            title = page.get("url", page_id)

        items.append({
            "id": f"notion_{page_id}",
            "user_id": user_id,
            "source": "notion",
            "source_id": page_id,
            "raw_content": json.dumps(page, ensure_ascii=False, default=str),
            "summary": title,
            "action_type": "review",
            "from_person": None,
            "status": None,
            "created_at": datetime.now().isoformat(),
        })
    return items


def sync_notion():
    from backend.db.store import get_session
    from backend.db.orm_models import IntegrationCredentialORM
    from backend.auth.models import User
    from sqlalchemy import select
    
    with get_session() as db:
        stmt = (
            select(IntegrationCredentialORM.user_id, User.sync_settings)
            .join(User, User.id == IntegrationCredentialORM.user_id)
            .where(IntegrationCredentialORM.source == "notion")
        )
        users = db.execute(stmt).all()
        for uid, settings in users:
            days = (settings or {}).get("notion", 14)
            run_sync(f"notion_{uid}", _fetch, user_id=uid, days=days)
