from datetime import datetime
from backend.tools.storage import search_items


def compute_daily_stats(date: str) -> dict:
    """
    특정 날짜의 완료·이월·응답시간 통계를 계산한다.
    date: "YYYY-MM-DD"
    """
    # TODO (#6): date 기반 필터링 + 실제 통계 구현
    done = search_items(status="done")
    pending = search_items(status="pending")
    return {
        "date": date,
        "completed": len(done),
        "pending": len(pending),
        "completion_rate": round(len(done) / max(len(done) + len(pending), 1), 2),
        "avg_response_minutes": None,   # TODO (#6)
        "note": "Week 2 구현 예정",
    }


def compute_kpi(period: str = "weekly") -> dict:
    """
    period: "weekly" | "monthly"
    주간/월간 KPI 집계.
    """
    # TODO (#6): period별 집계 구현
    return {
        "period": period,
        "avg_completion_rate": None,
        "overdue_ratio": None,
        "total_items": None,
        "note": "Phase 2 구현 예정",
    }


if __name__ == "__main__":
    print(compute_daily_stats("2026-05-20"))
