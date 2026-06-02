from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import chat
from backend.db.store import init_db

app = FastAPI(title="WhatToDo API")


@app.on_event("startup")
def startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")