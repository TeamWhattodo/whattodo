from math import exp, ceil
from datetime import datetime


def time_score(due_at: datetime | None, received_at: datetime) -> float:
    now = datetime.now()
    if due_at:
        hours_left = (due_at - now).total_seconds() / 3600
        if hours_left <= 0:
            return 1.0
        return 1 - exp(-3 / max(hours_left, 0.5))
    else:
        hours_elapsed = (now - received_at).total_seconds() / 3600
        return min(hours_elapsed / 72, 0.6)


def score_urgency(items: list[dict]) -> list[dict]:
    """
    WorkItem[] → urgency_level(1~5) + urgency_breakdown 추가 후 반환
    LLM 미사용. 수식만.
    """
    for item in items:
        due_at = (
            datetime.fromisoformat(item["due_at"])
            if item.get("due_at") else None
        )
        received_at = datetime.fromisoformat(item.get("created_at", datetime.now().isoformat()))

        t = time_score(due_at, received_at)
        item["urgency_level"]     = max(1, ceil(t * 5))
        item["urgency_breakdown"] = {"T": round(t, 3)}

    return sorted(items, key=lambda x: x["urgency_level"], reverse=True)


if __name__ == "__main__":
    from datetime import timedelta
    test = [
        {"id": "1", "due_at": (datetime.now() - timedelta(hours=2)).isoformat(),
         "created_at": datetime.now().isoformat()},
        {"id": "2", "due_at": None,
         "created_at": (datetime.now() - timedelta(hours=10)).isoformat()},
    ]
    for item in score_urgency(test):
        print(f"id={item['id']} urgency={item['urgency_level']} {item['urgency_breakdown']}")
