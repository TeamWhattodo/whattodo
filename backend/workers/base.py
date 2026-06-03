"""싱크 워커 공통 유틸."""
import logging
from datetime import datetime, timezone
from sqlalchemy import text
from backend.db.store import get_session
from backend.tools.storage import save_items

logger = logging.getLogger(__name__)


def run_sync(source: str, fetch_fn, *args, **kwargs) -> int:
    """
    공통 싱크 실행 래퍼.
    fetch_fn 호출 → DB 저장 → sync_log 갱신
    반환: 저장된 항목 수
    """
    _update_sync_log(source, "running")
    try:
        items: list[dict] = fetch_fn(*args, **kwargs)
        if not isinstance(items, list):
            items = []

        for item in items:
            item["synced_at"] = datetime.now(timezone.utc).isoformat()

        save_items(items)
        _update_sync_log(source, "success", len(items))
        logger.info(f"[{source}] sync 완료: {len(items)}건")
        return len(items)
    except Exception as e:
        _update_sync_log(source, "error", error=str(e))
        logger.error(f"[{source}] sync 실패: {e}")
        return 0


def _update_sync_log(source: str, status: str, count: int = 0, error: str = None):
    with get_session() as db:
        db.execute(text("""
            UPDATE sync_log
            SET last_synced_at = :now,
                status         = :status,
                items_count    = :count,
                error_message  = :error
            WHERE source = :source
        """), {
            "now": datetime.now(timezone.utc),
            "status": status,
            "count": count,
            "error": error,
            "source": source,
        })
