"""
문서 작성 툴 — n8n의 문서 작성(microsoftExcelTool) 노드 대응.

WorkCard 목록을 받아 Excel 또는 CSV 파일로 내보낸다.
Phase 1: CSV 인메모리 생성 (openpyxl 없이).
Phase 2: openpyxl로 서식 있는 .xlsx 생성 후 Google Drive 업로드.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from backend.models import WorkCard


def export_cards_to_csv(cards: list[WorkCard]) -> bytes:
    """WorkCard 목록을 UTF-8 BOM CSV 바이트로 반환. Streamlit download_button에 바로 사용 가능."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["id", "source", "from_person", "summary", "urgency_level",
                    "action_type", "due_at", "estimated_minutes", "status"],
    )
    writer.writeheader()
    for card in cards:
        writer.writerow({
            "id": card.id,
            "source": card.source,
            "from_person": card.from_person,
            "summary": card.summary,
            "urgency_level": card.urgency_level,
            "action_type": card.action_type,
            "due_at": card.due_at.isoformat() if card.due_at else "",
            "estimated_minutes": card.estimated_minutes,
            "status": card.status,
        })
    return ("﻿" + buf.getvalue()).encode("utf-8")


def export_cards_to_xlsx(cards: list[WorkCard]) -> bytes:
    """
    WorkCard 목록을 xlsx 바이트로 반환.
    TODO: Phase 2 — openpyxl 설치 후 서식 포함 구현.
    """
    raise NotImplementedError("Phase 2에서 openpyxl 기반으로 구현 예정")


def generate_filename(prefix: str = "briefing") -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{prefix}_{now}.csv"
