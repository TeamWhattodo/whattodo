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


def run_expense_pipeline(image_path: str) -> dict:
    """정산서 파이프라인."""
    from backend.tools.receipt import parse_receipt
    from backend.tools.expense import build_expense_report

    receipt_items = parse_receipt(image_path)
    report = build_expense_report(items=receipt_items, report_type="출장비")
    return report


if __name__ == "__main__":
    print("=== 브리핑 파이프라인 (mock) ===")
    for item in run_briefing_pipeline(use_mock=True):
        print(f"[{item['urgency_level']}] {item['summary']} ({item['source']})")
