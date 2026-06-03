import json
from backend.workers.base import run_sync
from backend.tools.slack_fetch import fetch_slack_all_items


def _fetch() -> list[dict]:
    raw = fetch_slack_all_items.func()
    try:
        data = json.loads(raw)
        return data.get("items", []) if isinstance(data, dict) else []
    except Exception:
        return []


def sync_slack():
    run_sync("slack", _fetch)
