from backend.tools.fetch import fetch_emails, fetch_slack_messages, fetch_jira_issues
from backend.tools.scoring import score_urgency
from backend.tools.classify import classify_items
from backend.mock_data import MOCK_WORK_ITEMS


def run_briefing_pipeline(use_mock: bool = True) -> list[dict]:
    """
    브리핑 파이프라인.
    use_mock=True  → mock 데이터 (Week 1~2)
    use_mock=False → 실데이터 (Week 2 이후)
    """
    if use_mock:
        items = list(MOCK_WORK_ITEMS)
        scored = sorted(items, key=lambda x: x["urgency_level"], reverse=True)
    else:
        gmail    = fetch_emails(since_hours=24)
        slack    = fetch_slack_messages(since_hours=24)
        jira     = fetch_jira_issues(due_within_days=7)
        items    = gmail + slack + jira
        scored   = score_urgency(items)

    targets    = [i for i in scored if i["urgency_level"] >= 3]
    classified = classify_items(targets)
    return classified


def run_expense_pipeline(receipt_text: str) -> dict:
    """정산서 파이프라인."""
    from backend.tools.receipt import parse_receipt_from_text
    from backend.tools.write_report import write_report

    receipt_items = parse_receipt_from_text(receipt_text)
    return write_report("expense_report", {"items": receipt_items})


if __name__ == "__main__":
    print("=== 브리핑 파이프라인 (mock) ===")
    for item in run_briefing_pipeline(use_mock=True):
        print(f"[{item['urgency_level']}] {item['summary']} ({item['source']})")
