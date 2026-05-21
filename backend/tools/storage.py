from backend.db.store import work_items_db as _db, expense_reports_db as _expense_db, ItemQuery as Item


def save_items(items: list[dict]) -> None:
    for item in items:
        if not _db.search(Item.id == item["id"]):
            _db.insert(item)


def get_pending_items() -> list[dict]:
    return _db.search(Item.status == "pending")


def get_item_by_id(item_id: str) -> dict | None:
    results = _db.search(Item.id == item_id)
    return results[0] if results else None


def search_items(query: str = "", status: str = None, source: str = None) -> list[dict]:
    results = _db.all()
    if status:
        results = [r for r in results if r.get("status") == status]
    if source:
        results = [r for r in results if r.get("source") == source]
    if query:
        q = query.lower()
        results = [r for r in results if q in (r.get("summary", "") + r.get("raw_content", "")).lower()]
    return results


def update_item_status(item_id: str, status: str) -> dict:
    _db.update({"status": status}, Item.id == item_id)
    return {"success": True, "item_id": item_id, "status": status}


def save_expense_report(report: dict) -> None:
    _expense_db.insert(report)


if __name__ == "__main__":
    test = [{"id": "test_001", "source": "gmail", "status": "pending",
             "summary": "테스트", "urgency_level": 3}]
    save_items(test)
    print("저장:", get_pending_items())
    update_item_status("test_001", "done")
    print("업데이트:", get_pending_items())
