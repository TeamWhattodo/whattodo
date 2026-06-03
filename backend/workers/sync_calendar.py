from backend.workers.base import run_sync
from backend.tools.calendar_fetch import fetch_calendar


def _fetch() -> list[dict]:
    items = fetch_calendar(days=14)
    return [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in items]


def sync_calendar():
    run_sync("calendar", _fetch)
