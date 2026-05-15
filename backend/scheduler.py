from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


async def run_daily_summary():
    ...


async def run_weekly_kpi():
    ...


def setup_scheduler():
    scheduler.add_job(run_daily_summary, "cron", hour=18, minute=0)
    scheduler.add_job(run_weekly_kpi, "cron", day_of_week="fri", hour=17, minute=0)
    scheduler.start()
