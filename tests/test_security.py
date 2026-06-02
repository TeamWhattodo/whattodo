import pytest

from backend.auth import security


def test_hash_and_verify_password():
    hashed = security.hash_password("supersecret")
    assert hashed != "supersecret"
    assert security.verify_password("supersecret", hashed) is True
    assert security.verify_password("wrong", hashed) is False


def test_jwt_roundtrip():
    token = security.create_access_token(user_id=42)
    assert isinstance(token, str)
    assert security.decode_access_token(token) == 42


def test_decode_invalid_token_returns_none():
    assert security.decode_access_token("garbage.token.value") is None
