from __future__ import annotations

from datetime import date
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

ACTION_AGENT_LOCAL_TOOLS: list[str] = [
    "search_past_items",
    "get_item_thread",
    "write_draft",
    "update_item_status",
    "create_calendar_block",
    "delete_calendar_block",
    "search_calendar_events",
]

ACTION_AGENT_MCP_TOOLS: list[str] = [
    "slack_get_thread_replies",
    "slack_post_message",
    "jira_update_issue",
    "API-patch-page",
]

def _build_system_prompt() -> str:
    today = date.today().strftime("%Y-%m-%d")
    return f"""\
당신은 액션 처리 전담 에이전트입니다.
오늘 날짜: {today}

## 원칙
- 사용자 요청에서 필요한 모든 정보(날짜·시간·제목 등)를 직접 파악해 툴을 즉시 호출하세요.
- 날짜·시간은 자연어("내일 오후 2시")를 오늘 날짜 기준으로 ISO 8601 형식으로 **에이전트가 직접 변환**합니다. 사용자에게 형식을 요구하지 마세요.
- 사용자가 "김대표 메시지", "계약서 메일" 등 자연어로 항목을 지칭하면 search_past_items로 검색해 item_id와 source_id를 먼저 확보하세요.
- **절대 금지**: 툴 호출 없이 "발송됐습니다", "완료됐습니다", "생성됐습니다" 등 완료 메시지를 만들어내지 마세요. 반드시 실제 툴 호출 결과를 기반으로만 완료 여부를 알려주세요.

## 툴 사용 순서

### 답장 초안 작성 (write_draft)
1. 사용자가 자연어로 항목 지칭 시 → search_past_items로 item_id 확보
2. get_item_thread(item_id, source) 호출해 맥락 확보 (source: gmail·slack·jira)
3. write_draft(item_id) 호출해 초안 생성
4. 초안을 사용자에게 보여주고 발송 여부 확인
※ 항목을 찾은 뒤 중간에 멈추지 말고 write_draft까지 연속 실행할 것

### Slack 메시지 발송 (slack_post_message)
1. search_past_items로 항목 조회 → source_id 확보 (형식: "C채널ID:thread_ts")
2. source_id를 콜론으로 분리 → channel_id(앞부분), thread_ts(뒷부분)
3. write_draft로 초안 생성 후 사용자에게 보여주고 발송 확인
4. 사용자 승인 시 slack_post_message(channel_id=channel_id, text=초안내용, thread_ts=thread_ts) 호출
   → 원본 메시지가 있던 채널에 스레드 답글로 전송됨
5. 툴 호출 결과의 ok 필드가 true일 때만 "발송됐습니다"라고 알릴 것

### 기타 발송·수정·삭제 액션
- jira_update_issue, API-patch-page, create_calendar_block, delete_calendar_block은 **처음 시도 시에만** 실행 내용을 사용자에게 보여주고 승인 요청
- 사용자가 "응", "맞아", "해줘", "확인", "예", "네", "ㅇㅇ" 등 긍정 응답을 하면 **즉시 툴을 호출**하고 결과를 반환. 다시 확인을 요청하지 말 것

## 사용 가능한 툴
search_past_items, get_item_thread, write_draft, update_item_status,
create_calendar_block, delete_calendar_block,
slack_get_thread_replies, slack_post_message, jira_update_issue, API-patch-page\
"""


def _build_tools(all_tools: list) -> list:
    """로컬 툴(이름 매칭) + MCP 툴(이름 매칭) 반환."""
    allowed = set(ACTION_AGENT_LOCAL_TOOLS) | set(ACTION_AGENT_MCP_TOOLS)
    return [t for t in all_tools if t.name in allowed]


_agent = None
_agent_date: str = ""


def _get_agent():
    global _agent, _agent_date
    today = date.today().strftime("%Y-%m-%d")
    if _agent is None or _agent_date != today:
        _agent = create_agent(
            model=get_llm("fast"),
            tools=_build_tools(load_all_tools()),
            system_prompt=_build_system_prompt(),
        )
        _agent_date = today
    return _agent


async def _run_async(messages: list) -> tuple[str, bool]:
    result = await _get_agent().ainvoke({"messages": messages})
    out_messages = result["messages"]
    output_text = out_messages[-1].content if out_messages else ""
    has_write = any(getattr(m, "name", "") == "write_draft" for m in out_messages)
    return output_text, has_write


def action_agent_node(state: WhatToDoState) -> dict:
    messages = state.get("messages") or [HumanMessage(content=state["user_input"])]
    text, has_write = _run(_run_async(messages))
    return {
        "results": {"action": {"text": text}},
        "has_write_output": has_write,
    }
