"""Notion 페이지 계층 구조 조회"""
import json
from langchain_core.tools import tool
from backend.config import settings


def _client():
    from notion_client import Client
    return Client(auth=settings.notion_api_token)


def _get_all_pages() -> list[dict]:
    try:
        client = _client()
        results = client.search(query="", filter={"property": "object", "value": "page"}).get("results", [])
        return results
    except Exception as e:
        return []


def _build_tree(pages: list[dict]) -> dict:
    """parent_id 기준으로 트리 구조 생성."""
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
        # title에 이미 이모지가 포함된 경우 icon 이모지 중복 추가 방지
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


@tool
def list_notion_pages() -> str:
    """Notion 워크스페이스의 전체 페이지를 계층 구조로 반환합니다. 페이지 생성 위치 선택 시 사용."""
    pages = _get_all_pages()
    if not pages:
        return json.dumps({"error": "Notion 페이지를 가져올 수 없습니다. 인증을 확인해주세요."}, ensure_ascii=False)
    tree = _build_tree(pages)
    formatted = _format_tree(tree["roots"])
    return json.dumps({"pages": formatted}, ensure_ascii=False, default=str)
