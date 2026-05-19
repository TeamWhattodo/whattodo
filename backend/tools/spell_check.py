"""
맞춤법 검사 툴 — n8n의 맞춤법 검사(httpRequestTool) 노드 대응.

외부 맞춤법 API에 텍스트를 보내고 교정 결과를 반환한다.
Phase 1: 부산대 맞춤법 검사기(비공식) 엔드포인트 사용.
Phase 2 전환 시 정식 API 키 발급 후 교체.
"""
from __future__ import annotations

import httpx

_SPELL_CHECK_URL = "https://speller.cs.pusan.ac.kr/results"


def check_spelling(text: str) -> dict:
    """
    텍스트 맞춤법 검사.
    반환: {"original": str, "corrected": str, "errors": list[dict]}
    """
    # TODO: Phase 2 — API 키 기반 정식 서비스로 교체
    try:
        response = httpx.post(
            _SPELL_CHECK_URL,
            data={"text1": text},
            timeout=10.0,
        )
        response.raise_for_status()
        return _parse_response(text, response.text)
    except httpx.HTTPError:
        return {"original": text, "corrected": text, "errors": [], "error": "맞춤법 API 연결 실패"}


def _parse_response(original: str, raw: str) -> dict:
    # TODO: 실제 응답 파싱 로직 구현
    return {
        "original": original,
        "corrected": original,
        "errors": [],
        "raw": raw,
    }
