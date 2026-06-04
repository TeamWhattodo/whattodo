import json
from backend.workers.base import run_sync
from backend.tools.slack_fetch import fetch_slack_all_items


def _fetch(user_id: int) -> list[dict]:
    # We directly use the client logic to fetch all items for the user
    from backend.tools.slack_fetch import _client
    import hashlib
    from datetime import datetime

    client = _client(user_id=user_id)
    try:
        ch_result = client.conversations_list(limit=200, types="public_channel")
        channels = [c for c in ch_result.data.get("channels", []) if c.get("is_member")]
    except Exception:
        return []

    all_items = []
    for ch in channels:
        channel_id = ch["id"]
        channel_name = ch.get("name", channel_id)
        try:
            msgs = client.conversations_history(channel=channel_id, limit=30).data.get("messages", [])
        except Exception:
            continue

        for msg in msgs:
            ts = msg.get("ts", "")
            text = msg.get("text", "")
            user = msg.get("user") or msg.get("username") or "unknown"
            if not text or msg.get("subtype"):
                continue

            source_id = f"{channel_id}:{ts}"
            all_items.append({
                "id": hashlib.md5(source_id.encode()).hexdigest(),
                "user_id": user_id,
                "source": "slack",
                "raw_content": text[:1000],
                "summary": f"[#{channel_name}] {text[:80]}{'...' if len(text) > 80 else ''}",
                "urgency_level": 3,
                "action_type": "reply",
                "from_person": user,
                "source_id": source_id,
                "created_at": datetime.utcfromtimestamp(float(ts)) if ts else datetime.utcnow(),
                "status": "pending",
            })
    return all_items


def sync_slack():
    from backend.db.store import get_session
    from backend.db.orm_models import IntegrationCredentialORM
    from sqlalchemy import select
    
    # 기본 글로벌 연동(1번 유저 취급)
    run_sync("slack", _fetch, user_id=1)
    
    # DB에 저장된 다른 유저들 토큰 기반 연동
    with get_session() as db:
        users = db.execute(select(IntegrationCredentialORM.user_id).where(IntegrationCredentialORM.source == "slack")).scalars().all()
        for uid in users:
            if uid == 1: continue # 1번은 위에서 처리함
            run_sync(f"slack_{uid}", _fetch, user_id=uid)
