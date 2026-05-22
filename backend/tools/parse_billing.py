from pathlib import Path


def parse_billing_data(file_path: str, month: str) -> dict:
    """
    CSV/Excel 정산 데이터 파싱.
    file_path: 파일 경로
    month: "YYYY-MM"
    반환: {"month": ..., "revenue": ..., "items": [...]}
    """
    # TODO (#6): CSV/Excel 파서 구현 (openpyxl / csv 모듈)
    return {
        "month": month,
        "file_path": file_path,
        "revenue": None,
        "refunds": None,
        "net": None,
        "items": [],
        "note": "Week 2 구현 예정",
    }


if __name__ == "__main__":
    print(parse_billing_data("billing_may.csv", "2026-05"))
