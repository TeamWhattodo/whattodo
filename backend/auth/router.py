"""인증 라우터 — register / login / logout / me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import security
from backend.auth.deps import ACCESS_TOKEN_NAME, REFRESH_TOKEN_NAME, get_current_user
from backend.auth.models import User
from backend.auth.schemas import LoginReq, RegisterReq, UserOut, UpdateUserReq
from backend.config import settings
from backend.db.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

def _invalid_credentials() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                         detail="아이디 또는 비밀번호가 올바르지 않습니다")


async def _set_tokens_and_cookies(response: Response, user: User, db: AsyncSession) -> None:
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    
    # DB 업데이트
    user.access_token = access_token
    user.refresh_token = refresh_token
    await db.commit()

    response.set_cookie(
        key=ACCESS_TOKEN_NAME,
        value=access_token,
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_days * 24 * 3600,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_secure,
        max_age=settings.jwt_refresh_expire_days * 24 * 3600,
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(req: RegisterReq, response: Response,
                   db: AsyncSession = Depends(get_db)) -> User:
    exists = (
        await db.execute(select(User).where(User.username == req.username))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다")
    user = User(username=req.username, password_hash=security.hash_password(req.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다")
    await db.refresh(user)
    await _set_tokens_and_cookies(response, user, db)
    return user


@router.post("/login", response_model=UserOut)
async def login(req: LoginReq, response: Response,
                db: AsyncSession = Depends(get_db)) -> User:
    user = (
        await db.execute(select(User).where(User.username == req.username))
    ).scalar_one_or_none()
    if user is None or not security.verify_password(req.password, user.password_hash):
        raise _invalid_credentials()
    await _set_tokens_and_cookies(response, user, db)
    return user


@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get(REFRESH_TOKEN_NAME)
    if not refresh_token:
        raise _invalid_credentials()
    
    user_id = security.decode_refresh_token(refresh_token)
    if user_id is None:
        raise _invalid_credentials()
        
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or user.refresh_token != refresh_token:
        raise _invalid_credentials()
        
    await _set_tokens_and_cookies(response, user, db)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    refresh_token = request.cookies.get(REFRESH_TOKEN_NAME)
    if refresh_token:
        user_id = security.decode_refresh_token(refresh_token)
        if user_id:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user:
                user.access_token = None
                user.refresh_token = None
                await db.commit()

    response.delete_cookie(key=ACCESS_TOKEN_NAME, path="/", httponly=True,
                           samesite="lax", secure=settings.cookie_secure)
    response.delete_cookie(key=REFRESH_TOKEN_NAME, path="/", httponly=True,
                           samesite="lax", secure=settings.cookie_secure)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=UserOut)
async def update_me(
    req: UpdateUserReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    if req.password:
        user.password_hash = security.hash_password(req.password)
    
    if req.sync_settings is not None:
        user.sync_settings = req.sync_settings

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/me")
async def delete_me(
    response: Response,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    from backend.db.orm_models import (
        IntegrationCredentialORM,
        SyncLogORM,
        WorkItemORM,
        SessionORM,
        ExpenseReportORM
    )
    from sqlalchemy import delete

    # 연관 데이터 삭제 (CASCADE 효과)
    await db.execute(delete(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == user.id))
    await db.execute(delete(SyncLogORM).where(SyncLogORM.user_id == user.id))
    await db.execute(delete(WorkItemORM).where(WorkItemORM.user_id == user.id))
    await db.execute(delete(SessionORM).where(SessionORM.user_id == str(user.id)))
    await db.execute(delete(ExpenseReportORM).where(ExpenseReportORM.user_id == user.id))
    
    # 유저 삭제
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()

    # 쿠키 제거
    response.delete_cookie(key=ACCESS_TOKEN_NAME, path="/", httponly=True, samesite="lax", secure=settings.cookie_secure)
    response.delete_cookie(key=REFRESH_TOKEN_NAME, path="/", httponly=True, samesite="lax", secure=settings.cookie_secure)

    return {"ok": True}
