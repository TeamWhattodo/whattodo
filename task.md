# Action Agent 구현 현황

## 역할

`action_agent.py`는 **액션 처리 전담 에이전트**이다.
search_agent/report_agent가 조회·분석 역할이라면, action_agent는 실제로 외부 시스템에 무언가를 **실행**한다.

- 답장 초안 작성
- WorkItem 상태 변경 (done / snoozed / pending)
- Gmail 읽기·발송·삭제
- Slack 스레드 조회·답글 발송·삭제
- Jira 이슈 상태 업데이트 (MCP)
- Notion 페이지 수정 (MCP)
- Google Calendar 일정 생성·삭제·조회

---

## 서비스별 CRUD 현황

| 서비스 | 읽기 | 생성/발송 | 삭제 |
|---|---|---|---|
| Google Calendar | ✅ 테스트 완료 | ✅ 테스트 완료 | ✅ 테스트 완료 |
| Gmail | ✅ 테스트 완료 | ✅ 테스트 완료 | ✅ 테스트 완료 |
| Slack | ✅ 테스트 완료 | ✅ 테스트 완료 | ✅ 테스트 완료 |
| Jira | ✅ 테스트 완료 | ✅ 테스트 완료 | ✅ 테스트 완료 |
| Notion | ✅ 테스트 완료 | ✅ 테스트 완료 | ✅ 테스트 완료 |

---

## 툴 목록

### 로컬 툴 (ACTION_AGENT_LOCAL_TOOLS)

- [o] `search_past_items` — TinyDB에서 WorkItem을 키워드/상태/출처로 검색
- [o] `get_item_thread` — 특정 item의 스레드 전체 조회 (Gmail/Slack 실연결 완료)
- [o] `write_draft` — item_id로 항목 조회 후 LLM(smart 티어)으로 답장 초안 생성
- [o] `update_item_status` — WorkItem 상태를 done/snoozed/pending으로 변경
- [o] `send_gmail` — Gmail 이메일 발송 (thread_id로 답장 지원, 사용자 확인 후 실행)
- [o] `trash_gmail` — Gmail 메시지 휴지통 이동 (사용자 확인 후 실행)
- [o] `create_calendar_block` — Google Calendar 일정 생성
- [o] `delete_calendar_block` — Google Calendar 일정 삭제 (사용자 확인 후 실행)
- [o] `search_calendar_events` — Google Calendar 일정 키워드 검색 (event_id 포함 반환)

### MCP / 외부 툴 (ACTION_AGENT_MCP_TOOLS)

- [o] `slack_get_thread_replies` — Slack 스레드 답글 조회
- [o] `slack_post_message` — Slack 채널 메시지 발송 (thread_ts 지원, 원본 채널 스레드 답글)
- [o] `slack_delete_message` — Slack 메시지 삭제 (사용자 확인 후 실행)
- [o] `jira_update_issue` — Jira 이슈 상태 변경 (MCP 연결 완료)
- [o] `API-patch-page` — Notion 페이지 수정 (MCP 연결 완료)

---

## 구현 체크리스트

### 1. tools_registry.py 등록 누락 수정 ✅

- [o] `get_item_thread`, `create_calendar_block` @tool 래퍼 추가 및 LOCAL_TOOLS 등록
- [o] 시스템 프롬프트에 오늘 날짜 자동 주입
- [o] 대화 맥락 유지 (messages history action_agent에 전달)
- [o] 확인 후 실행 흐름 동작 확인

### 2. Calendar 실구현 ✅

- [o] Google OAuth 스코프에 `calendar.events` 추가
- [o] `create_calendar_block` — Google Calendar API 실연결, 중복 체크
- [o] `delete_calendar_block` — 이벤트 삭제
- [o] `search_calendar_events` — 키워드 검색 (event_id 포함)

### 3. get_item_thread 실데이터 연결 ✅

- [o] WorkItem 모델에 `source_id` 필드 추가
- [o] Gmail threadId → source_id 저장
- [o] Gmail 스레드 조회 연결 (`threads().get()`)
- [o] `fetch_slack_as_items` 신규 구현 (Slack → WorkItem + source_id → TinyDB)
- [o] Slack 스레드 조회 연결 (source_id channel_id:ts → conversations_replies)
- [o] `slack_post_message` 발송 시 sent 메시지 TinyDB 저장 (삭제 시 참조)
- [o] briefing_agent에 fetch_gmail/fetch_calendar/fetch_slack_as_items 연결
- [o] _extract_response intent 기반으로 수정 (MemorySaver 누적 결과 방지)
- [x] Jira 이슈 댓글 조회 연결 (MCP 미연결, 추후 구현)

### 4. Jira CRUD 완성 ✅

- [o] uvx PATH 미등록 문제 해결 (`_find_uvx()` 자동 탐색)
- [o] jira_update_issue 포함 71개 Jira 툴 연결 확인
- [o] action_agent에 jira_get_all_projects, jira_get_issue, jira_get_transitions, jira_create_issue, jira_update_issue, jira_transition_issue, jira_delete_issue, jira_add_comment 등록
- [o] 이슈 생성 시 jira_get_all_projects 먼저 조회하도록 프롬프트 개선 (프로젝트 키 직접 요구 제거)
- [o] 이슈 생성·상태변경·삭제 UI 테스트 완료

### 5. Notion CRUD 완성 ✅

- [o] API-patch-page 포함 22개 Notion 툴 연결 확인
- [o] action_agent에 API-post-search, API-patch-page, API-post-page, API-delete-a-block, API-retrieve-a-page 등록
- [o] `list_notion_pages` 신규 툴 구현 — 계층 구조(부모→자식 들여쓰기)로 페이지 목록 반환
- [o] notion-client 패키지 설치 및 venv 등록
- [o] Notion 페이지 생성 시 위치 선택 플로우 구현 (list_notion_pages → 사용자 선택 → API-post-page)
- [o] 페이지 생성·수정·삭제 UI 테스트 완료

### 6. write_draft 맥락 확보 흐름 완성 ✅

- [o] get_item_thread → write_draft → slack_post_message / send_gmail 전체 플로우 검증

### 8. Gmail CRUD 완성 ✅

- [o] Google OAuth 스코프에 `gmail.send`, `gmail.modify` 추가
- [o] `send_gmail` — Gmail 발송 (thread_id 답장 지원)
- [o] `trash_gmail` — Gmail 휴지통 이동
- [o] action_agent Gmail 발송·삭제 플로우 명시

### 9. Slack 삭제 추가 ✅

- [o] `slack_delete_message` 신규 구현 (channel_id + ts)
- [o] slack_post_message 발송 메시지 TinyDB 저장 (삭제 시 역참조 가능)
- [o] action_agent 삭제 플로우 명시 ([발송됨] 항목만 삭제)
- [o] search_agent 키워드 검색 개선 (핵심어 추출, 재시도 안내)

### 7. 사용자 확인(Human-in-the-loop) 처리

- [o] send_gmail, slack_post_message, create/delete_calendar_block, slack_delete_message, trash_gmail — LLM 레벨 확인 흐름 동작
- [x] LangGraph interrupt() 기반 Human-in-the-loop 구현 (추후)
