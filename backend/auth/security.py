"""비밀번호 해싱(bcrypt)·JWT 발급/검증."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from backend.config import settings

_ALGORITHM = "HS256"


def _secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("jwt_secret 미설정 — .env에 jwt_secret을 지정하세요")
    return settings.jwt_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """유효하면 user_id, 아니면 None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
