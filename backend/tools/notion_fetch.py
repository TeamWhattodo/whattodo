import json
from langchain_core.tools import tool
from backend.config import settings


def _client():
    from notion_client import Client
    return Client(auth=settings.notion_api_token)


def _safe(fn):
    try:
        return json.dumps(fn(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


def _extract_title(obj: dict) -> str:
    if obj["object"] == "page":
        for v in obj.get("properties", {}).values():
            if v.get("type") == "title":
                return "".join(t.get("plain_text", "") for t in v.get("title", []))
    elif obj["object"] == "database":
        return "".join(t.get("plain_text", "") for t in obj.get("title", []))
    return ""


@tool
def notion_search(query: str, page_size: int = 20) -> str:
    """Notion에서 페이지와 데이터베이스를 키워드로 검색합니다."""
    try:
        result = _client().search(query=query, page_size=page_size)
        data = {
            "ok": True,
            "has_more": result.get("has_more", False),
            "results": [
                {
                    "id": r["id"],
                    "type": r["object"],
                    "title": _extract_title(r),
                    "url": r.get("url"),
                    "last_edited_time": r.get("last_edited_time"),
                }
                for r in result.get("results", [])
            ],
        }
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def notion_get_page(page_id: str) -> str:
    """Notion 페이지 속성을 조회합니다."""
    def _fn():
        page = _client().pages.retrieve(page_id=page_id)
        return {"ok": True, "id": page["id"], "url": page.get("url"), "properties": page.get("properties")}
    return _safe(_fn)


@tool
def notion_get_page_content(page_id: str) -> str:
    """Notion 페이지 본문 블록을 조회합니다."""
    def _fn():
        blocks = _client().blocks.children.list(block_id=page_id)
        simplified = [
            {
                "id": b["id"],
                "type": b["type"],
                "text": "".join(
                    t.get("plain_text", "")
                    for t in b.get(b["type"], {}).get("rich_text", [])
                ),
            }
            for b in blocks.get("results", [])
        ]
        return {"ok": True, "blocks": simplified}
    return _safe(_fn)


@tool
def notion_query_database(database_id: str, page_size: int = 50) -> str:
    """Notion 데이터베이스 항목을 조회합니다."""
    def _fn():
        result = _client().databases.query(database_id=database_id, page_size=page_size)
        return {
            "ok": True,
            "has_more": result.get("has_more", False),
            "results": [
                {
                    "id": r["id"],
                    "title": _extract_title(r),
                    "url": r.get("url"),
                    "last_edited_time": r.get("last_edited_time"),
                    "properties": r.get("properties"),
                }
                for r in result.get("results", [])
            ],
        }
    return _safe(_fn)


@tool
def notion_create_page(parent_id: str, title: str, content: str = "", parent_type: str = "page") -> str:
    """Notion 페이지를 생성합니다. parent_type은 'page' 또는 'database'. 반드시 사용자 확인 후 실행."""
    def _fn():
        parent = {"database_id": parent_id} if parent_type == "database" else {"page_id": parent_id}
        children = []
        if content:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": content}}]},
            })
        page = _client().pages.create(
            parent=parent,
            properties={"title": {"title": [{"text": {"content": title}}]}},
            children=children,
        )
        return {"ok": True, "id": page["id"], "url": page.get("url")}
    return _safe(_fn)


NOTION_TOOLS = [
    notion_search,
    notion_get_page,
    notion_get_page_content,
    notion_query_database,
    notion_create_page,
]
