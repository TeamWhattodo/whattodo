"""
자리비움 서비스 — n8n의 자리비움 상태 확인(IF) + 부재중 응답(Gmail reply) 노드 대응.

isWorking 플래그를 관리하고, 메일 트리거 수신 시
자리비움 상태이면 자동 답장을 발송한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AbsenceState:
    is_working: bool = True
    away_message: str = "현재 자리를 비우고 있습니다. 복귀 후 연락드리겠습니다."
    return_at: datetime | None = None
    auto_replied_ids: set[str] = field(default_factory=set)


_state = AbsenceState()


def set_absence(away_message: str, return_at: datetime | None = None) -> None:
    _state.is_working = False
    _state.away_message = away_message
    _state.return_at = return_at
    _state.auto_replied_ids.clear()


def set_working() -> None:
    _state.is_working = True
    _state.return_at = None


def is_working() -> bool:
    return _state.is_working


def get_away_message() -> str:
    msg = _state.away_message
    if _state.return_at:
        msg += f"\n복귀 예정: {_state.return_at.strftime('%Y-%m-%d %H:%M')}"
    return msg


def handle_incoming_email(email_id: str, from_address: str, subject: str) -> bool:
    """
    n8n 메일 트리거 → 자리비움 상태 확인 → 부재중 응답 흐름.
    자리비움 상태이고 미처리 메일이면 자동 답장을 발송하고 True 반환.
    """
    if _state.is_working:
        return False
    if email_id in _state.auto_replied_ids:
        return False

    _send_auto_reply(from_address, subject)
    _state.auto_replied_ids.add(email_id)
    return True


def _send_auto_reply(to: str, original_subject: str) -> None:
    # TODO: connectors/gmail.py reply() 연결
    print(f"[자동답장] → {to} | Re: {original_subject}\n{get_away_message()}")
