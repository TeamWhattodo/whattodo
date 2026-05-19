"""
알람 툴 — n8n의 알람(toolCode) 노드 대응.

마감 임박 항목을 에이전트가 감지하면 이 툴을 호출해
Slack DM 또는 이메일로 알림을 발송한다.
Phase 1: 콘솔 출력 + 세션 알람 큐.
Phase 2: Slack Web API / Gmail SMTP 실제 발송으로 교체.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class AlarmChannel(str, Enum):
    CONSOLE = "console"
    SLACK = "slack"
    EMAIL = "email"


@dataclass
class Alarm:
    item_id: str
    message: str
    channel: AlarmChannel
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent: bool = False


_alarm_queue: list[Alarm] = []


def trigger_alarm(
    item_id: str,
    message: str,
    channel: AlarmChannel = AlarmChannel.CONSOLE,
) -> Alarm:
    """알람을 생성하고 발송한다."""
    alarm = Alarm(item_id=item_id, message=message, channel=channel)
    _alarm_queue.append(alarm)
    _dispatch(alarm)
    return alarm


def get_pending_alarms() -> list[Alarm]:
    return [a for a in _alarm_queue if not a.sent]


def get_all_alarms() -> list[Alarm]:
    return list(_alarm_queue)


def _dispatch(alarm: Alarm) -> None:
    if alarm.channel == AlarmChannel.CONSOLE:
        print(f"[ALARM] {alarm.triggered_at.isoformat()} | {alarm.message}")
        alarm.sent = True
    elif alarm.channel == AlarmChannel.SLACK:
        # TODO: connectors/slack.py send_dm() 연결
        print(f"[SLACK ALARM] {alarm.message}")
        alarm.sent = True
    elif alarm.channel == AlarmChannel.EMAIL:
        # TODO: connectors/gmail.py send() 연결
        print(f"[EMAIL ALARM] {alarm.message}")
        alarm.sent = True
