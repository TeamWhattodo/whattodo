from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.db.database import get_db
from backend.auth.deps import get_current_user
from backend.auth.models import User
from backend.db.orm_models import IntegrationCredentialORM
from backend.utils.encryption import encrypt_token, decrypt_token
from pydantic import BaseModel

router = APIRouter(prefix="/integrations", tags=["integrations"])

class IntegrationState(BaseModel):
    source: str
    connected: bool

class SaveIntegrationReq(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: str | None = None  # ISO format string if needed

@router.get("/", response_model=List[IntegrationState])
async def get_integrations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """현재 유저의 연동된 플랫폼 상태(목록) 반환"""
    tokens = (await db.execute(select(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == user.id))).scalars().all()
    connected_sources = {t.source for t in tokens}
    
    # 예시: 지원하는 플랫폼 목록 (추후 하드코딩 혹은 DB 관리)
    supported = ["google", "slack", "jira", "notion"]
    
    return [
        IntegrationState(source=src, connected=(src in connected_sources))
        for src in supported
    ]

@router.post("/{source}")
async def save_integration(
    source: str, 
    req: SaveIntegrationReq, 
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """최초 연동 시 토큰 저장 (암호화) 및 유효성 검증"""
    import json
    
    # 토큰 유효성 검증
    try:
        if source == "slack":
            from slack_sdk import WebClient
            creds = json.loads(req.access_token)
            client = WebClient(token=creds["bot_token"])
            client.auth_test()
        elif source == "jira":
            from jira import JIRA
            creds = json.loads(req.access_token)
            client = JIRA(server=creds["base_url"], basic_auth=(creds["email"], creds["api_token"]))
            client.myself()
        elif source == "notion":
            from notion_client import Client
            client = Client(auth=req.access_token)
            client.users.me()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 {source} 토큰(또는 설정값)입니다. 다시 확인해주세요.")
        
    token_obj = (await db.execute(
        select(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == user.id, IntegrationCredentialORM.source == source)
    )).scalar_one_or_none()
    
    if not token_obj:
        token_obj = IntegrationCredentialORM(user_id=user.id, source=source)
        db.add(token_obj)
        
    token_obj.credentials_data = encrypt_token(req.access_token)
    
    await db.commit()
    
    # Trigger initial sync immediately
    if source == "slack":
        from backend.workers.sync_slack import sync_slack
        background_tasks.add_task(sync_slack)
    elif source == "jira":
        from backend.workers.sync_jira import sync_jira
        background_tasks.add_task(sync_jira)
    elif source == "notion":
        from backend.workers.sync_notion import sync_notion
        background_tasks.add_task(sync_notion)
        
    return {"ok": True, "source": source}

@router.delete("/{source}")
async def disconnect_integration(source: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """연동 해제 (해당 플랫폼 토큰 삭제)"""
    token_obj = (await db.execute(
        select(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == user.id, IntegrationCredentialORM.source == source)
    )).scalar_one_or_none()
    
    if token_obj:
        await db.delete(token_obj)
        await db.commit()
        return {"ok": True, "source": source}
    
    raise HTTPException(status_code=404, detail="연동된 정보를 찾을 수 없습니다.")


from fastapi.responses import RedirectResponse
from fastapi import Request

@router.get("/google/login")
async def google_login(user: User = Depends(get_current_user)):
    from backend.google_auth import get_auth_url
    url = get_auth_url(user.id)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(request: Request, state: str, code: str, background_tasks: BackgroundTasks):
    from backend.google_auth import handle_callback
    try:
        handle_callback(state, code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    from backend.workers.sync_gmail import sync_gmail
    from backend.workers.sync_calendar import sync_calendar
    background_tasks.add_task(sync_gmail)
    background_tasks.add_task(sync_calendar)
    
    return {"ok": True}
