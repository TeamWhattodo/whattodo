from backend.tools.storage import search_items as _search, get_item_by_id


def search_past_items(query: str = "", date_range: str = "7d", status: str = None, source: str = None) -> list[dict]:
    """
    저장된 WorkItem을 조건으로 검색한다.
    date_range: "today" | "7d" | "30d" (현재 구현은 date_range 무시)
    status: "done" | "pending" | "snoozed" | None (전체)
    """
    # TODO (#5): date_range 필터링 구현
    return _search(query=query, status=status, source=source)


def get_item_thread(item_id: str, source: str) -> list[dict]:
    """특정 항목의 스레드 전체를 조회한다. (Week 2: 실데이터 연결)"""
    # TODO (#5): 실데이터 스레드 조회 연결
    item = get_item_by_id(item_id)
    return [{"item_id": item_id, "source": source, "item": item, "thread_note": "Week 2 구현 예정"}]


if __name__ == "__main__":
    print(search_past_items(status="pending"))
