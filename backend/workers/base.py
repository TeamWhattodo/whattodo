"""싱크 워커 공통 유틸."""
import logging
from datetime import datetime, timezone
from sqlalchemy import text
from backend.db.store import get_session
from backend.tools.storage import save_items
from backend.tools.deadline_extractor import extract_deadlines

logger = logging.getLogger(__name__)


def run_sync(source: str, fetch_fn, user_id: int = 1, *args, **kwargs) -> int:
    """
    공통 싱크 실행 래퍼.
    fetch_fn 호출 → DB 저장 → sync_log 갱신
    반환: 저장된 항목 수
    """
    _update_sync_log(source, user_id, "running")
    try:
        items: list[dict] = fetch_fn(user_id=user_id, *args, **kwargs) if 'user_id' in fetch_fn.__code__.co_varnames else fetch_fn(*args, **kwargs)
        if not isinstance(items, list):
            items = []

        for item in items:
            item["synced_at"] = datetime.now(timezone.utc).isoformat()
            item["user_id"] = user_id

        items = extract_deadlines(items)
        save_items(items)
        _update_sync_log(source, user_id, "success", len(items))
        logger.info(f"[User {user_id}][{source}] sync 완료: {len(items)}건")
        return len(items)
    except Exception as e:
        _update_sync_log(source, user_id, "error", error=str(e))
        logger.error(f"[User {user_id}][{source}] sync 실패: {e}")
        return 0


def _update_sync_log(source: str, user_id: int, status: str, count: int = 0, error: str = None):
    with get_session() as db:
        db.execute(text("""
            INSERT INTO sync_log (user_id, source, last_synced_at, status, items_count, error_message)
            VALUES (:user_id, :source, :now, :status, :count, :error)
            ON CONFLICT (user_id, source) DO UPDATE
            SET last_synced_at = :now,
                status         = :status,
                items_count    = :count,
                error_message  = :error
        """), {
            "now": datetime.now(timezone.utc),
            "status": status,
            "count": count,
            "error": error,
            "source": source,
            "user_id": user_id,
        })
