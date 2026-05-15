from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/gmail/callback")
async def gmail_callback(code: str, state: str | None = None):
    ...


@router.get("/slack/callback")
async def slack_callback(code: str, state: str | None = None):
    ...
