"""
Google OAuth2 토큰 관리 (DB 연동 버전).
- 최초 인증: get_auth_url() → redirect → handle_callback()
- 이후 사용: get_credentials() (자동 갱신)
"""
import json
import threading
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from backend.config import settings
from backend.db.store import get_session
from backend.db.orm_models import IntegrationCredentialORM
from backend.utils.encryption import encrypt_token, decrypt_token
from sqlalchemy import select

_TOKEN_LOCK = threading.Lock()

# 간단한 인메모리 세션 관리 (다중 유저용)
# 프로덕션에서는 Redis나 DB를 사용하는 것이 좋습니다.
_OAUTH_STATES = {}

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

_REDIRECT_URI = "http://localhost:8501"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_REDIRECT_URI],
        }
    }


def get_auth_url(user_id: int) -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = _REDIRECT_URI
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _OAUTH_STATES[state] = {
        "user_id": user_id,
        "code_verifier": getattr(flow, "code_verifier", None)
    }
    return auth_url


def handle_callback(state: str, code: str) -> None:
    if state not in _OAUTH_STATES:
        raise ValueError("Invalid state parameter or session expired.")
        
    session_data = _OAUTH_STATES.pop(state)
    user_id = session_data["user_id"]
    code_verifier = session_data["code_verifier"]

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = _REDIRECT_URI
    flow.fetch_token(code=code, code_verifier=code_verifier)
    
    _save_token(user_id, flow.credentials)


def get_credentials(user_id: int) -> Credentials | None:
    with get_session() as db:
        token_obj = db.execute(
            select(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == user_id, IntegrationCredentialORM.source == "google")
        ).scalar_one_or_none()
        
        if not token_obj or not token_obj.credentials_data:
            return None
            
        try:
            creds_json = decrypt_token(token_obj.credentials_data)
            creds_dict = json.loads(creds_json)
        except Exception:
            return None

    with _TOKEN_LOCK:
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(user_id, creds)
            
    return creds


def is_authenticated(user_id: int) -> bool:
    creds = get_credentials(user_id)
    return creds is not None and creds.valid


def _save_token(user_id: int, creds: Credentials) -> None:
    creds_json = creds.to_json()
    encrypted_creds = encrypt_token(creds_json)
    
    with get_session() as db:
        token_obj = db.execute(
            select(IntegrationCredentialORM).where(IntegrationCredentialORM.user_id == user_id, IntegrationCredentialORM.source == "google")
        ).scalar_one_or_none()
        
        if not token_obj:
            token_obj = IntegrationCredentialORM(user_id=user_id, source="google")
            db.add(token_obj)
            
        token_obj.credentials_data = encrypted_creds
