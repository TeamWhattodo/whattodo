import os
from cryptography.fernet import Fernet
from backend.config import settings

def _get_cipher() -> Fernet:
    """Return Fernet cipher using OAUTH_ENCRYPTION_KEY from settings."""
    key = settings.oauth_encryption_key
    if not key:
        raise RuntimeError("oauth_encryption_key 미설정 - .env에 OAUTH_ENCRYPTION_KEY를 지정하세요")
    return Fernet(key.encode("utf-8"))

def encrypt_token(token: str | None) -> str | None:
    """토큰 암호화 (문자열 -> 암호화된 문자열)"""
    if not token:
        return None
    cipher = _get_cipher()
    return cipher.encrypt(token.encode("utf-8")).decode("utf-8")

def decrypt_token(encrypted_token: str | None) -> str | None:
    """토큰 복호화 (암호화된 문자열 -> 원본 문자열)"""
    if not encrypted_token:
        return None
    cipher = _get_cipher()
    return cipher.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
