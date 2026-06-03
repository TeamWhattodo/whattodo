from backend.workers.base import run_sync
from backend.tools.gmail_fetch import fetch_gmail


def _fetch() -> list[dict]:
    items = fetch_gmail(max_results=50, query="")
    return [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]


def sync_gmail():
    run_sync("gmail", _fetch)
