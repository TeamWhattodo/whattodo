import json
from datetime import datetime
from backend.workers.base import run_sync
from backend.tools.jira_fetch import jira_search_issues


def _fetch() -> list[dict]:
    raw = jira_search_issues.func(
        jql="statusCategory not in (Done) ORDER BY updated DESC",
        max_results=50,
    )
    try:
        data = json.loads(raw)
        issues = data if isinstance(data, list) else data.get("issues", [])
    except Exception:
        return []

    items = []
    for issue in (issues or []):
        key = issue.get("key", "")
        fields = issue.get("fields", {})
        items.append({
            "id": f"jira_{key}",
            "source": "jira",
            "source_id": key,
            "raw_content": json.dumps(issue, ensure_ascii=False, default=str),
            "summary": fields.get("summary", key),
            "action_type": "review",
            "from_person": (fields.get("assignee") or {}).get("displayName"),
            "due_at": fields.get("duedate"),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        })
    return items


def sync_jira():
    run_sync("jira", _fetch)
