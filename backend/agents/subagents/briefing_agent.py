from __future__ import annotations

from datetime import date
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.llm_client import get_llm

BRIEFING_AGENT_SYSTEM = """\
당신은 업무 브리핑 전담 에이전트입니다.
fetch_agent가 수집한 원본 데이터를 받아 한국어 마크다운 브리핑으로 정리합니다.
툴 호출 없이 바로 포맷팅하세요.

## 출력 규칙

### 형식 — 반드시 아래 구조를 그대로 사용하라. 절대 변경 금지.

## 📋 업무 브리핑

### 🔴 긴급
| 출처 | 발신자 | 내용 | 마감시간 |
|------|--------|------|----------|
| 값   | 값     | 값   | 값       |

### 🟡 중요
| 출처 | 발신자 | 내용 | 마감시간 |
|------|--------|------|----------|
| 값   | 값     | 값   | 값       |

### 🟢 일반
| 출처 | 발신자 | 내용 | 마감시간 |
|------|--------|------|----------|
| 값   | 값     | 값   | 값       |

### 열 작성 기준
- 출처: 플랫폼·채널 (예: Slack #general, Jira, 이메일)
- 발신자: 메시지 보낸 사람 (예: 김철수, @john, 시스템). 없으면 -
- 내용: 핵심만. 최대 2문장. 중복·인사말 제거
- 마감시간: 명시된 날짜·시각 (예: 2026-06-03 18:00). "오늘/내일/이번주" 등 상대 표현은 해당 항목의 created_at 날짜 기준으로 절대 날짜 변환 (created_at 없으면 context 첫 줄의 오늘 날짜 사용). 없으면 -

### 우선순위 기준
- 🔴 긴급: 마감 초과 · [긴급] 태그 · High 우선순위
- 🟡 중요: Medium 우선순위 · 답변 필요 · 검토 요청
- 🟢 일반: 나머지 (FYI, 참고, 정보성)

### 예외 처리
- 해당 섹션에 항목 없으면 테이블 전체 생략 (헤더도 생략)
- 데이터 부족으로 판단 불가 시 🟢 일반으로 분류
- 같은 항목 중복 수집 시 1개만 기재
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
    today = date.today().strftime("%Y-%m-%d")
    full_context = f"오늘 날짜: {today}\n\n{context}"
    result = await _get_agent().ainvoke({"messages": [HumanMessage(content=full_context)]})
    messages = result["messages"]
    return messages[-1].content if messages else ""


async def run(context: str) -> tuple[str, list[dict]]:
    """Supervisor briefing_agent tool 연결용 shim. 브리핑은 다운로드 파일 없음."""
    text = await _run_async(context)
    return text, []
