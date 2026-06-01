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


# ── 페이지 계층 구조 헬퍼 (list_notion_pages 전용) ────────────────────────────

def _get_all_pages() -> list[dict]:
    try:
        client = _client()
        results = client.search(query="", filter={"property": "object", "value": "page"}).get("results", [])
        return results
    except Exception:
        return []


def _build_tree(pages: list[dict]) -> dict:
    nodes = {}
    for p in pages:
        pid = p["id"]
        title = ""
        props = p.get("properties", {})
        if "title" in props:
            title_arr = props["title"].get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_arr) if title_arr else "(제목 없음)"
        elif "Name" in props:
            title_arr = props["Name"].get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_arr) if title_arr else "(제목 없음)"
        icon = p.get("icon", {})
        emoji = icon.get("emoji", "") if icon and icon.get("type") == "emoji" else ""
        nodes[pid] = {
            "id": pid,
            "title": title,
            "emoji": emoji,
            "parent_id": None,
            "children": [],
            "url": p.get("url", ""),
        }
        parent = p.get("parent", {})
        if parent.get("type") == "page_id":
            nodes[pid]["parent_id"] = parent["page_id"]

    roots = []
    for pid, node in nodes.items():
        par = node["parent_id"]
        if par and par in nodes:
            nodes[par]["children"].append(node)
        else:
            roots.append(node)
    return {"roots": roots, "all": nodes}


def _format_tree(nodes: list[dict], depth: int = 0) -> list[dict]:
    result = []
    for node in nodes:
        prefix = "  " * depth
        title = node["title"]
        if node["emoji"] and not title.startswith(node["emoji"]):
            display_title = f"{node['emoji']} {title}"
        elif not node["emoji"] and not any(ord(c) > 0x2600 for c in title[:2]):
            display_title = f"📄 {title}"
        else:
            display_title = title
        result.append({
            "id": node["id"],
            "display": f"{prefix}{display_title}",
            "title": title,
            "depth": depth,
        })
        if node["children"]:
            result.extend(_format_tree(node["children"], depth + 1))
    return result


# ── @tool 정의 ────────────────────────────────────────────────────────────────

@tool
def list_notion_pages() -> str:
    """Notion 워크스페이스의 전체 페이지를 계층 구조로 반환합니다. 페이지 생성 위치 선택 시 사용."""
    pages = _get_all_pages()
    if not pages:
        return json.dumps({"error": "Notion 페이지를 가져올 수 없습니다. 인증을 확인해주세요."}, ensure_ascii=False)
    tree = _build_tree(pages)
    formatted = _format_tree(tree["roots"])
    return json.dumps({"pages": formatted}, ensure_ascii=False, default=str)


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


@tool
def notion_update_page(page_id: str, title: str) -> str:
    """Notion 페이지 제목을 수정합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        page = _client().pages.update(
            page_id=page_id,
            properties={"title": {"title": [{"text": {"content": title}}]}},
        )
        return {"ok": True, "id": page["id"], "url": page.get("url")}
    return _safe(_fn)


@tool
def notion_delete_block(block_id: str) -> str:
    """Notion 블록(페이지 포함)을 보관함으로 이동합니다. 반드시 사용자 확인 후 실행."""
    def _fn():
        _client().blocks.delete(block_id=block_id)
        return {"ok": True, "block_id": block_id}
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


NOTION_TOOLS = [
    notion_search,
    notion_get_page,
    notion_get_page_content,
    notion_create_page,
    notion_update_page,
    notion_delete_block,
    notion_query_database,
]
