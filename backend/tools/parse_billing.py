from pathlib import Path


def parse_billing_data(billing_text: str, month: str) -> dict:
    """
    추출된 정산 텍스트 파싱.
    billing_text: 추출된 정산 데이터 텍스트
    month: "YYYY-MM"
    반환: {"month": ..., "revenue": ..., "items": [...]}
    """
    # TODO (#6): 텍스트 파서 구현
    return {
        "month": month,
        "revenue": None,
        "refunds": None,
        "net": None,
        "items": [],
        "note": "Week 2 구현 예정",
    }


if __name__ == "__main__":
    print(parse_billing_data("정산 텍스트 샘플", "2026-05"))
