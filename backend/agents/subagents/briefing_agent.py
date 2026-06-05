from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm_client import get_llm

BRIEFING_AGENT_SYSTEM = """\
당신은 업무 브리핑 전담 에이전트입니다.
fetch_agent가 수집한 원본 데이터를 받아 한국어 마크다운 브리핑으로 정리합니다.
툴 호출 없이 바로 포맷팅하세요.

## 출력 규칙

### 형식 — 반드시 아래 구조를 그대로 사용하라. 절대 변경 금지.

## 📋 업무 브리핑

### 🔴 긴급
| 출처 | 내용 | 마감일 |
|------|------|--------|
| 값   | 값   | 값     |

### 🟡 중요
| 출처 | 내용 | 마감일 |
|------|------|--------|
| 값   | 값   | 값     |

### 🟢 일반
| 출처 | 내용 | 마감일 |
|------|------|--------|
| 값   | 값   | 값     |

### 열 작성 기준
- 출처: 플랫폼·채널 (예: Slack, Jira, Gmail)
- 내용: 핵심만. 최대 2문장. 중복·인사말 제거
- 마감일: deadline 값을 "MM/DD HH:MM" 형식으로 표시. 없으면 "-"

### 우선순위 기준
- 🔴 긴급(urgent): 마감 초과 · [긴급] 태그 · 즉시 처리 필요
- 🟡 중요(important): 승인·검토·리뷰 요청 · 배포 관련
- 🟢 일반(normal): 나머지 (FYI, 참고, 정보성)

### 예외 처리
- 해당 섹션에 항목 없으면 테이블 전체 생략 (헤더도 생략)
- 같은 항목 중복 수집 시 1개만 기재
"""


async def run(context: str) -> tuple[str, list[dict]]:
    text = (await get_llm("fast").ainvoke([
        SystemMessage(content=BRIEFING_AGENT_SYSTEM),
        HumanMessage(content=context),
    ])).content.strip()
    return text, []
