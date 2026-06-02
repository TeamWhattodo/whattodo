"""
Google OAuth2 토큰 관리.
- 최초 인증: get_auth_url() → redirect → handle_callback()
- 이후 사용: get_credentials() (자동 갱신)
"""
import json
import threading
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from backend.config import settings

_TOKEN_LOCK = threading.Lock()

_PKCE_PATH = Path("data/.oauth_state.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

_TOKEN_PATH = Path("data/google_token.json")
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


def get_auth_url() -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = _REDIRECT_URI
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # PKCE code_verifier를 파일에 저장해 콜백 시 재사용
    _PKCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PKCE_PATH.write_text(json.dumps({
        "code_verifier": getattr(flow, "code_verifier", None),
        "state": state,
    }))
    return auth_url


def handle_callback(code: str) -> None:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES)
    flow.redirect_uri = _REDIRECT_URI

    code_verifier = None
    if _PKCE_PATH.exists():
        try:
            saved = json.loads(_PKCE_PATH.read_text())
            code_verifier = saved.get("code_verifier")
        except Exception:
            pass
        finally:
            _PKCE_PATH.unlink(missing_ok=True)

    flow.fetch_token(code=code, code_verifier=code_verifier)
    _save_token(flow.credentials)


def get_credentials() -> Credentials | None:
    if not _TOKEN_PATH.exists():
        return None
    with _TOKEN_LOCK:
        creds = Credentials.from_authorized_user_info(
            json.loads(_TOKEN_PATH.read_text()), SCOPES
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
    return creds


def is_authenticated() -> bool:
    creds = get_credentials()
    return creds is not None and creds.valid


def _save_token(creds: Credentials) -> None:
    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_PATH.write_text(creds.to_json())
