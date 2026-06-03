from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.store import init_db
from backend.routers import chat
from backend.workers import sync_gmail, sync_slack, sync_calendar, sync_jira, sync_notion


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    scheduler = BackgroundScheduler()
    scheduler.add_job(sync_gmail,    "interval", minutes=5,  id="sync_gmail")
    scheduler.add_job(sync_slack,    "interval", minutes=2,  id="sync_slack")
    scheduler.add_job(sync_calendar, "interval", minutes=5,  id="sync_calendar")
    scheduler.add_job(sync_jira,     "interval", minutes=10, id="sync_jira")
    scheduler.add_job(sync_notion,   "interval", minutes=15, id="sync_notion")
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(title="WhatToDo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
