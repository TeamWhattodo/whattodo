"""
스케줄러 — n8n의 시간 트리거(12시, 13시, 18시) + 주간 KPI 노드 대응.

APScheduler로 cron 잡을 등록하고 WorkAssistantAgent의
run_scheduled()를 호출한다.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


async def _run_agent_scheduled(hour: int) -> None:
    from backend.agents.agent import WorkAssistantAgent
    agent = WorkAssistantAgent()
    result = agent.run_scheduled(hour)
    print(f"[스케줄] {hour}시 실행 완료:\n{result}")


async def run_daily_summary():
    """18시 — 오늘 처리 현황 요약. n8n 18시 트리거 대응."""
    await _run_agent_scheduled(18)


async def run_lunch_reminder():
    """13시 — 점심 후 우선순위 재정렬. n8n 13시 트리거 대응."""
    await _run_agent_scheduled(13)


async def run_morning_check():
    """12시 — 오전 미처리 항목 리마인드. n8n 12시 트리거 대응."""
    await _run_agent_scheduled(12)


async def run_weekly_kpi():
    """금요일 17시 — 주간 KPI 리포트."""
    # TODO: KPIReport 생성 및 Slack/이메일 발송
    ...


def setup_scheduler():
    scheduler.add_job(run_morning_check, "cron", hour=12, minute=0)
    scheduler.add_job(run_lunch_reminder, "cron", hour=13, minute=0)
    scheduler.add_job(run_daily_summary, "cron", hour=18, minute=0)
    scheduler.add_job(run_weekly_kpi, "cron", day_of_week="fri", hour=17, minute=0)
    scheduler.start()
