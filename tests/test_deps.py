import pytest
from fastapi import HTTPException

from backend.auth import deps, security


class _FakeRequest:
    def __init__(self, cookies):
        self.cookies = cookies


def test_extract_user_id_valid_cookie():
    token = security.create_access_token(user_id=7)
    req = _FakeRequest({"token": token})
    assert deps.extract_user_id(req) == 7


def test_extract_user_id_no_cookie_raises_401():
    req = _FakeRequest({})
    with pytest.raises(HTTPException) as exc:
        deps.extract_user_id(req)
    assert exc.value.status_code == 401


def test_extract_user_id_bad_cookie_raises_401():
    req = _FakeRequest({"token": "bad"})
    with pytest.raises(HTTPException) as exc:
        deps.extract_user_id(req)
    assert exc.value.status_code == 401
