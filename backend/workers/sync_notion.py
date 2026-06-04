import json
from datetime import datetime
from backend.workers.base import run_sync


def _fetch(user_id: int) -> list[dict]:
    try:
        from backend.tools.notion_fetch import _client
        client = _client(user_id=user_id)
        response = client.search(query="", page_size=30)
        pages = response.get("results", [])
    except Exception:
        return []

    items = []
    for page in pages:
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
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        })
    return items


def sync_notion():
    from backend.db.store import get_session
    from backend.db.orm_models import IntegrationCredentialORM
    from sqlalchemy import select
    
    # 기본 글로벌 연동(1번 유저 취급)
    run_sync("notion", _fetch, user_id=1)
    
    # DB에 저장된 다른 유저들 토큰 기반 연동
    with get_session() as db:
        users = db.execute(select(IntegrationCredentialORM.user_id).where(IntegrationCredentialORM.source == "notion")).scalars().all()
        for uid in users:
            if uid == 1: continue # 1번은 위에서 처리함
            run_sync(f"notion_{uid}", _fetch, user_id=uid)
