from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

_USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,30}$")


class RegisterReq(BaseModel):
    username: str
    password: str
    name: str | None = None
    department: str | None = None
    position: str | None = None

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("username은 3~30자 영숫자여야 합니다")
        return v

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 최소 8자여야 합니다")
        return v


class LoginReq(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    name: str | None = None
    department: str | None = None
    position: str | None = None
