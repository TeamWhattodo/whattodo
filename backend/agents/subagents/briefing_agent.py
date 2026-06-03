from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import _run

BRIEFING_SYSTEM = """\
당신은 업무 브리핑 포맷 전담 에이전트입니다.
fetch_agent가 조회한 WorkItem 데이터를 받아 사용자가 보기 좋은 마크다운으로 변환합니다.

━━ 긴급도 기준 ━━
🔴 긴급  (urgency_level 4~5) — 즉시 처리 필요
🟡 중요  (urgency_level 3)   — 오늘 안에 처리
🟢 일반  (urgency_level 1~2) — 여유롭게 처리

━━ 출력 형식 ━━

## 📋 업무 브리핑

### 🔴 긴급
- [소스] 발신자 | 제목 | 날짜

### 🟡 중요
- [소스] 발신자 | 제목 | 날짜

### 🟢 일반
- [소스] 발신자 | 제목 | 날짜

---
총 N건 | 긴급 N건 · 중요 N건 · 일반 N건

━━ 규칙 ━━
- 데이터가 없는 긴급도 섹션은 생략
- 각 섹션 최대 10건 표시, 초과 시 "외 N건" 표기
- 소스는 [Gmail] [Slack] [Jira] [Notion] [Calendar] 형식
- urgency_level 없으면 🟢 일반으로 분류
- 실제 데이터만 출력. 가상 데이터 금지\
"""


async def _run_async(fetch_result: str, user_request: str) -> str:
    llm = get_llm("fast")
    messages = [
        SystemMessage(content=BRIEFING_SYSTEM),
        HumanMessage(content=f"사용자 요청: {user_request}\n\n수집된 데이터:\n{fetch_result}"),
    ]
    response = await llm.ainvoke(messages)
    return response.content


async def run(fetch_result: str, user_request: str = "") -> tuple[str, dict]:
    """Supervisor briefing_agent tool 연결용 shim."""
    text = await _run_async(fetch_result, user_request)
    return text, {}


def briefing_agent_node(fetch_result: str, user_request: str = "") -> str:
    return _run(_run_async(fetch_result, user_request))
