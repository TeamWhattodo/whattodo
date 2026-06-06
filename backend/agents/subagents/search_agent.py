from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

_BASE_TOOLS     = {"search_past_items", "search_company_docs", "get_item_thread"}
_GMAIL_TOOLS    = {"fetch_gmail"}
_CALENDAR_TOOLS = {"fetch_calendar", "search_calendar_events"}
_NOTION_TOOLS   = {"notion_search", "notion_get_page_content"}
_SLACK_TOOLS    = {"slack_search_messages"}
_JIRA_TOOLS     = {"jira_search_issues"}

SEARCH_AGENT_SYSTEM = """\
당신은 특정 정보 조회 전담 에이전트입니다. (전체 브리핑이 아닌 사용자가 명시한 소스·키워드 검색)
툴이 반환한 실제 데이터만 출력하세요. 절대 데이터를 만들어내지 마세요.

## 소스별 툴 선택
- 메일·이메일 → fetch_gmail(max_results=20)
- 캘린더·일정 → fetch_calendar(days=7) 또는 search_calendar_events
- Notion 문서·페이지 → notion_search 후 결과가 있으면 notion_get_page_content로 내용 확인
  ※ 사내 규정·정책은 search_company_docs 사용, Notion 내용 조회는 notion_search 사용 (혼용 금지)
- Slack 메시지 검색 → slack_search_messages
- Jira 업무·이슈 조회 → search_past_items(source="jira") 로 DB에서 먼저 조회
  ※ 사용자가 실시간·최신 데이터를 명시적으로 요청할 때만 jira_search_issues(jql=...) 사용
  ※ 상태 필터: 해야할 일→status="todo", 진행 중→status="pending", 완료→status="done"
  ※ 미완료 전체(해야할 일+진행 중)를 원하면 status 파라미터 없이 source="jira"만 지정하고 status != "done" 항목을 반환
- 사내 규정·정책·한도 → search_company_docs
- 저장된 과거 업무 항목 → search_past_items
- 특정 항목 스레드·상세 내용 → search_past_items로 item_id 확보 후 get_item_thread

## 검색 방법
- search_past_items query에는 핵심 키워드만 입력 (문장 전체 금지)
- 첫 검색에서 안 나오면 query를 더 짧게 줄여서 재시도

## 상태값 한글 변환 규칙 (절대 준수)
status 필드의 영문 값을 절대 그대로 출력하지 마세요. 반드시 아래 한글로 변환해서 출력하세요:
- "todo" → 해야할 일
- "pending" → 진행 중
- "done" → 완료
- null / 없음 → -

## 출력 규칙
- 결과가 없으면 "해당 항목을 찾을 수 없습니다"로 출력
- 절대 툴 호출 없이 메일·일정·문서 내용을 지어내지 마세요
- 절대 raw JSON을 그대로 출력하지 마세요. 반드시 아래 소스별 포맷으로 가공해서 출력하세요.

### Jira 업무 출력 포맷
총 N개 업무를 마크다운 목록으로 출력하세요:

**Jira 업무 목록 (N개)**

1. **[업무 제목]**
   - 상태: [한글 상태값]
   - 담당자: from_person (없으면 "-")

### 메일 출력 포맷
- 발신자·제목·날짜를 정리해서 목록으로 출력

### 캘린더 출력 포맷
- 일정 제목·날짜·시간을 정리해서 목록으로 출력\
"""


def _detect_sources(text: str) -> set[str]:
    t = text.lower()
    sources = set()
    if any(w in t for w in ["gmail", "메일", "이메일", "mail"]):
        sources.add("gmail")
    if any(w in t for w in ["calendar", "캘린더", "일정", "스케줄"]):
        sources.add("calendar")
    if any(w in t for w in ["notion", "노션", "문서", "페이지"]):
        sources.add("notion")
    if any(w in t for w in ["slack", "슬랙", "채널"]):
        sources.add("slack")
    if any(w in t for w in ["jira", "지라", "이슈", "티켓"]):
        sources.add("jira")
    return sources


def _build_tools(all_tools: list, sources: set[str] = None) -> list:
    allowed = set(_BASE_TOOLS)
    if sources is None or "gmail" in sources:
        allowed |= _GMAIL_TOOLS
    if sources is None or "calendar" in sources:
        allowed |= _CALENDAR_TOOLS
    if sources is None or "notion" in sources:
        allowed |= _NOTION_TOOLS
    if sources is None or "slack" in sources:
        allowed |= _SLACK_TOOLS
    if sources is None or "jira" in sources:
        allowed |= _JIRA_TOOLS
    return [t for t in all_tools if t.name in allowed]


def _get_agent(sources: set[str] = None):
    return create_agent(
        model=get_llm("fast"),
        tools=_build_tools(load_all_tools(), sources),
        system_prompt=SEARCH_AGENT_SYSTEM,
    )


_STATUS_KO = {"todo": "해야할 일", "pending": "진행 중", "done": "완료"}


def _format_jira_items(items: list) -> str:
    lines = [f"**Jira 업무 목록 ({len(items)}개)**\n"]
    for i, item in enumerate(items, 1):
        status = _STATUS_KO.get(item.get("status") or "", item.get("status") or "-")
        person = item.get("from_person") or "-"
        lines.append(f"{i}. **{item.get('summary', '')}**")
        lines.append(f"   - 상태: {status}")
        lines.append(f"   - 담당자: {person}")
    return "\n".join(lines)


def _postprocess(text: str) -> str:
    import json as _json

    stripped = text.strip()
    # LLM이 raw JSON을 그대로 출력한 경우 Python에서 직접 포맷
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = _json.loads(stripped)
            items = None
            if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("source") == "jira":
                items = data
            elif isinstance(data, dict):
                candidate = data.get("items") or []
                if candidate and isinstance(candidate[0], dict) and candidate[0].get("source") == "jira":
                    items = candidate
            if items:
                return _format_jira_items(items)
        except Exception:
            pass

    # 일반 텍스트 내 영문 status 값 한글 치환
    for en, ko in _STATUS_KO.items():
        text = text.replace(f'"status": "{en}"', f'"status": "{ko}"')
        text = text.replace(f"status: {en}", f"status: {ko}")
        text = text.replace(f"(상태: {en})", f"(상태: {ko})")
    return text


async def _run_async(user_input: str) -> tuple[str, bool]:
    sources = _detect_sources(user_input)
    result = await _get_agent(sources).ainvoke({"messages": [HumanMessage(content=user_input)]})
    messages = result["messages"]
    output_text = messages[-1].content if messages else ""
    return _postprocess(output_text), False


async def run(query: str) -> tuple[str, bool]:
    """Supervisor search_agent tool 연결용 shim."""
    return await _run_async(query)


def search_agent_node(state: WhatToDoState) -> dict:
    text, has_write = _run(_run_async(state["user_input"]))
    return {
        "results": {"search": {"text": text}},
        "has_write_output": has_write,
    }
