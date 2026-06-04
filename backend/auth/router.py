"""인증 라우터 — register / login / logout / me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import security
from backend.auth.deps import COOKIE_NAME, get_current_user
from backend.auth.models import User
from backend.auth.schemas import LoginReq, RegisterReq, UserOut
from backend.config import settings
from backend.db.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

def _invalid_credentials() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                         detail="아이디 또는 비밀번호가 올바르지 않습니다")


def _set_token_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=security.create_access_token(user_id),
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_days * 24 * 3600,
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
    _set_token_cookie(response, user.id)
    return user


@router.post("/login", response_model=UserOut)
async def login(req: LoginReq, response: Response,
                db: AsyncSession = Depends(get_db)) -> User:
    user = (
        await db.execute(select(User).where(User.username == req.username))
    ).scalar_one_or_none()
    if user is None or not security.verify_password(req.password, user.password_hash):
        raise _invalid_credentials()
    _set_token_cookie(response, user.id)
    return user


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True,
                           samesite="lax", secure=settings.cookie_secure)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
