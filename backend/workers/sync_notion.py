import json
from datetime import datetime
from backend.workers.base import run_sync


def _fetch() -> list[dict]:
    try:
        from notion_client import Client
        from backend.config import settings
        client = Client(auth=settings.notion_api_token)
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
    run_sync("notion", _fetch)
