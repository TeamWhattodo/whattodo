from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.llm_client import get_llm

BRIEFING_AGENT_SYSTEM = """\
당신은 업무 브리핑 전담 에이전트입니다.
fetch_agent가 수집한 원본 데이터를 받아 한국어 마크다운 브리핑으로 정리합니다.
툴 호출 없이 바로 포맷팅하세요.

출력 형식:
## 📋 업무 브리핑

### 🔴 긴급
- 출처 · 내용 · 시각

### 🟡 중요
- 출처 · 내용 · 시각

### 🟢 일반
- 출처 · 내용 · 시각

긴급도 기준: 마감 초과·[긴급] 태그·High 우선순위 → 🔴 / Medium·답변 필요 → 🟡 / 나머지 → 🟢
"""


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent(
            model=get_llm("smart"),
            tools=[],
            system_prompt=BRIEFING_AGENT_SYSTEM,
        )
    return _agent


async def _run_async(context: str) -> str:
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=context)]})
    messages = result["messages"]
    return messages[-1].content if messages else ""


async def run(context: str) -> tuple[str, list[dict]]:
    """Supervisor briefing_agent tool 연결용 shim. 브리핑은 다운로드 파일 없음."""
    text = await _run_async(context)
    return text, []
