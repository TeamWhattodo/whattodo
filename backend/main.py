from fastapi import FastAPI
from backend.routers import auth

app = FastAPI(title="WhatToDo", version="0.1.0")
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
