"""인증 의존성 — 쿠키 JWT → User."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import security
from backend.auth.models import User
from backend.db.database import get_db

ACCESS_TOKEN_NAME = "access_token"
REFRESH_TOKEN_NAME = "refresh_token"

def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다")


def extract_user_id(request: Request) -> int:
    """쿠키에서 JWT를 읽어 user_id 반환. 실패 시 401."""
    token = request.cookies.get(ACCESS_TOKEN_NAME)
    if not token:
        raise _unauthorized()
    user_id = security.decode_access_token(token)
    if user_id is None:
        raise _unauthorized()
    return user_id


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = extract_user_id(request)
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise _unauthorized()
    return user
