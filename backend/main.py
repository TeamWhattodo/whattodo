from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.store import init_db
from backend.db.database import init_db as auth_init_db
from backend.routers import chat, integrations
from backend.auth import router as auth_router
from backend.workers import sync_gmail, sync_slack, sync_calendar, sync_jira, sync_notion


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await auth_init_db()

    scheduler = BackgroundScheduler()
    scheduler.add_job(sync_gmail,    "interval", minutes=5,  id="sync_gmail",    next_run_time=datetime.now())
    scheduler.add_job(sync_slack,    "interval", minutes=2,  id="sync_slack",    next_run_time=datetime.now())
    scheduler.add_job(sync_calendar, "interval", minutes=5,  id="sync_calendar", next_run_time=datetime.now())
    scheduler.add_job(sync_jira,     "interval", minutes=10, id="sync_jira",     next_run_time=datetime.now())
    scheduler.add_job(sync_notion,   "interval", minutes=15, id="sync_notion",   next_run_time=datetime.now())
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(title="WhatToDo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8501", "http://127.0.0.1:8501"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
