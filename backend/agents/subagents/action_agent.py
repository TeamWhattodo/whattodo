from __future__ import annotations

from datetime import date
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import WhatToDoState
from backend.agents.llm_client import get_llm
from backend.agents.tools_registry import load_all_tools, _run

ACTION_AGENT_TOOLS: list[str] = [
    "search_past_items",
    "get_item_thread",
    "write_draft",
    "update_item_status",
    "create_calendar_block",
    "delete_calendar_block",
    "search_calendar_events",
    "send_gmail",
    "trash_gmail",
    "slack_get_thread_replies",
    "slack_post_message",
    "slack_delete_message",
    "jira_list_projects",
    "jira_get_issue",
    "jira_get_transitions",
    "jira_create_issue",
    "jira_update_issue",
    "jira_transition_issue",
    "jira_delete_issue",
    "jira_add_comment",
    "list_notion_pages",
    "notion_search",
    "notion_get_page",
    "notion_create_page",
    "notion_update_page",
    "notion_delete_block",
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

### Gmail 발송 (send_gmail)
1. search_past_items로 원본 메일 조회 → from_person(수신자), source_id(threadId) 확보
2. write_draft로 초안 생성 후 사용자에게 보여주고 발송 확인
3. 사용자 승인 시 send_gmail(to=수신자이메일, subject=제목, body=초안내용, thread_id=threadId) 호출
4. 툴 결과 success=true일 때만 "발송됐습니다"라고 알릴 것

### Gmail 삭제 (trash_gmail)
1. search_past_items로 항목 조회 → source_id(threadId) 확보
2. get_item_thread로 스레드 내 message_id 확인
3. 삭제할 메일 내용을 사용자에게 보여주고 확인 요청
4. 사용자 승인 시 trash_gmail(message_id) 호출

### Slack 메시지 삭제 (slack_delete_message)
1. "방금 보낸 메시지" 삭제 요청 시 → search_past_items(query="발송됨")으로 from_person="me" 항목 검색
2. 그 외 특정 메시지 삭제 요청 시 → search_past_items로 해당 내용 검색
3. 찾은 항목의 source_id에서 channel_id:ts 분리
4. 삭제할 메시지 내용을 사용자에게 보여주고 확인 요청
5. 사용자 승인 시 slack_delete_message(channel_id, ts) 호출
6. 툴 결과의 ok 필드가 true일 때만 "삭제됐습니다"라고 알릴 것
※ 절대로 원본 채널 메시지(받은 메시지)를 삭제하지 말 것 — 반드시 "[발송됨]"이 붙은 항목만 삭제

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

### Jira 이슈 관리
- 생성: jira_list_projects로 프로젝트 목록 먼저 조회 → 사용자에게 프로젝트 선택 요청 → jira_create_issue(project_key, summary, issue_type="Task") 호출
  ※ 프로젝트 키를 사용자에게 직접 묻지 말 것. 항상 jira_list_projects로 먼저 조회할 것
- 조회: jira_get_issue(issue_key)
- 상태 변경: jira_get_transitions(issue_key)로 전환 목록 확인 → jira_transition_issue(issue_key, transition_id)
- 업데이트: jira_update_issue(issue_key, ...) — 사용자 확인 후 실행
- 삭제: jira_delete_issue(issue_key) — 사용자 확인 후 실행
- 댓글: jira_add_comment(issue_key, comment)

### Notion 페이지 관리
- 생성 절차:
  1. list_notion_pages()로 전체 페이지를 계층 구조로 조회
  2. 계층 구조(들여쓰기로 부모-자식 표현)를 사용자에게 보여줌:
     예) 📁 What To Do
          ├ 📄 문서1
          └ 📄 문서2
  3. **사용자가 직접 위치를 선택할 때까지 기다릴 것. 자동으로 선택해서 생성 금지**
  4. 사용자가 위치를 선택하면 notion_create_page(parent_id=<선택한_id>, title=<제목>) 호출
- 조회: notion_search(query)로 검색 → notion_get_page(page_id)로 상세 확인
- 수정: notion_update_page(page_id, title) — 사용자 확인 후 실행
- 블록 삭제: notion_delete_block(block_id) — 사용자 확인 후 실행

## 사용 가능한 툴
search_past_items, get_item_thread, write_draft, update_item_status,
send_gmail, trash_gmail,
create_calendar_block, delete_calendar_block, search_calendar_events,
slack_get_thread_replies, slack_post_message, slack_delete_message,
jira_list_projects, jira_get_issue, jira_get_transitions, jira_create_issue, jira_update_issue, jira_transition_issue, jira_delete_issue, jira_add_comment,
list_notion_pages, notion_search, notion_get_page, notion_create_page, notion_update_page, notion_delete_block\
"""


def _build_tools(all_tools: list) -> list:
    allowed = set(ACTION_AGENT_TOOLS)
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
