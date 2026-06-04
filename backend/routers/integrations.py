from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.db.database import get_db
from backend.auth.deps import get_current_user
from backend.auth.models import User
from backend.db.orm_models import OAuthTokenORM
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
    tokens = (await db.execute(select(OAuthTokenORM).where(OAuthTokenORM.user_id == user.id))).scalars().all()
    connected_sources = {t.source for t in tokens}
    
    # 예시: 지원하는 플랫폼 목록 (추후 하드코딩 혹은 DB 관리)
    supported = ["gmail", "slack", "jira", "notion", "calendar"]
    
    return [
        IntegrationState(source=src, connected=(src in connected_sources))
        for src in supported
    ]

@router.post("/{source}")
async def save_integration(
    source: str, 
    req: SaveIntegrationReq, 
    user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    """최초 연동 시 토큰 저장 (암호화)"""
    token_obj = (await db.execute(
        select(OAuthTokenORM).where(OAuthTokenORM.user_id == user.id, OAuthTokenORM.source == source)
    )).scalar_one_or_none()
    
    if not token_obj:
        token_obj = OAuthTokenORM(user_id=user.id, source=source)
        db.add(token_obj)
        
    token_obj.access_token = encrypt_token(req.access_token)
    token_obj.refresh_token = encrypt_token(req.refresh_token) if req.refresh_token else None
    
    await db.commit()
    return {"ok": True, "source": source}

@router.delete("/{source}")
async def disconnect_integration(source: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """연동 해제 (해당 플랫폼 토큰 삭제)"""
    token_obj = (await db.execute(
        select(OAuthTokenORM).where(OAuthTokenORM.user_id == user.id, OAuthTokenORM.source == source)
    )).scalar_one_or_none()
    
    if token_obj:
        await db.delete(token_obj)
        await db.commit()
        return {"ok": True, "source": source}
    
    raise HTTPException(status_code=404, detail="연동된 정보를 찾을 수 없습니다.")
