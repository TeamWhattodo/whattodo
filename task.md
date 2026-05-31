# Action Agent 구현 현황

## 역할

`action_agent.py`는 **액션 처리 전담 에이전트**이다.
search_agent/report_agent가 조회·분석 역할이라면, action_agent는 실제로 외부 시스템에 무언가를 **실행**한다.

- 답장 초안 작성
- WorkItem 상태 변경 (done / snoozed / pending)
- Slack 스레드 조회 및 메시지 발송 (원본 채널 스레드 답글)
- Jira 이슈 상태 업데이트
- Notion 페이지 수정
- Google Calendar 일정 생성·삭제·조회

---

## 툴 목록

### 로컬 툴 (ACTION_AGENT_LOCAL_TOOLS)

- [o] `search_past_items` — TinyDB에서 WorkItem을 키워드/상태/출처로 검색
- [o] `get_item_thread` — 특정 item의 스레드 전체 조회 (Gmail/Slack 실연결 완료)
- [o] `write_draft` — item_id로 항목 조회 후 LLM(smart 티어)으로 답장 초안 생성
- [o] `update_item_status` — WorkItem 상태를 done/snoozed/pending으로 변경
- [o] `create_calendar_block` — Google Calendar 일정 생성 (실 API 연결 완료)
- [o] `delete_calendar_block` — Google Calendar 일정 삭제 (사용자 확인 후 실행)
- [o] `search_calendar_events` — Google Calendar 일정 키워드 검색 (event_id 포함 반환)

### MCP / 외부 툴 (ACTION_AGENT_MCP_TOOLS)

- [o] `slack_get_thread_replies` — Slack 스레드 답글 조회 (slack_sdk 직접 연결)
- [o] `slack_post_message` — Slack 채널에 메시지 전송 (thread_ts 지원, 원본 채널 스레드 답글)
- [x] `jira_update_issue` — Jira 이슈 상태 변경 (MCP mcp-atlassian, .env 토큰 미설정 시 비활성)
- [x] `API-patch-page` — Notion 페이지 수정 (MCP @notionhq/notion-mcp-server, .env 토큰 미설정 시 비활성)

---

## 구현 체크리스트

### 1. tools_registry.py 등록 누락 수정 ✅

- [o] `get_item_thread` 에 `@tool` 래퍼 추가
- [o] `create_calendar_block` 에 `@tool` 래퍼 추가
- [o] 두 툴을 `LOCAL_TOOLS` 리스트에 추가
- [o] 시스템 프롬프트에 오늘 날짜 자동 주입 (날짜 파싱 오류 해결)
- [o] 대화 맥락 유지 (messages history action_agent에 전달)
- [o] 확인 후 실행 흐름 동작 확인 (create_calendar_block, write_draft)

### 2. create_calendar_block 실구현 ✅

- [o] Google OAuth 스코프에 `calendar.events` 추가
- [o] Google Calendar API 연결 및 이벤트 생성 (`events().insert()`)
- [o] 중복 일정 체크 로직
- [o] `delete_calendar_block` 추가 (Google Calendar 이벤트 삭제)
- [o] `search_calendar_events` 추가 (제목 키워드로 event_id 포함 검색)
- [o] search_agent에 `search_calendar_events`, `fetch_calendar` 추가
- [o] orchestrator 키워드 보강 ("일정", "삭제", "생성", "캘린더")
- [o] 확인 루프 방지 — 긍정 응답 시 즉시 실행

### 3. get_item_thread 실데이터 연결 ✅

- [o] WorkItem 모델에 `source_id` 필드 추가
- [o] `gmail_fetch.py` — threadId를 source_id에 저장
- [o] Gmail 스레드 조회 연결 (Gmail API `threads().get()`)
- [o] `fetch_slack_as_items` 신규 구현 (Slack → WorkItem + source_id → TinyDB)
- [o] Slack 스레드 조회 연결 (source_id channel_id:ts → conversations_replies)
- [o] `slack_post_message` thread_ts 파라미터 추가 (원본 채널 스레드 답글)
- [o] briefing_agent에 `fetch_gmail`, `fetch_calendar`, `fetch_slack_as_items` 연결
- [o] orchestrator 라우팅 키워드 보강 ("가져와", "수집", "Slack", "항목", "스레드")
- [o] `_extract_response` intent 기반으로 수정 (MemorySaver 누적 결과 오버라이드 방지)
- [o] action_agent hallucination 방지 및 Slack 발송 플로우 명시
- [x] Jira 이슈 댓글 조회 연결 (MCP 미연결, 추후 구현)

### 6. write_draft 맥락 확보 흐름 완성 ✅

- [o] `get_item_thread` → `write_draft` → `slack_post_message` 전체 플로우 검증 완료

### 4. jira_update_issue MCP 연결 검증

- [x] `.env`에 `JIRA_API_TOKEN`, `JIRA_EMAIL`, `JIRA_BASE_URL` 설정
- [x] `uvx mcp-atlassian` 설치 확인
- [x] MCP 툴 이름 `jira_update_issue` 실제 노출 이름과 일치 여부 확인

### 5. API-patch-page (Notion) MCP 연결 검증

- [x] `.env`에 `NOTION_API_TOKEN` 설정
- [x] `npx @notionhq/notion-mcp-server` 설치 확인
- [x] MCP 툴 이름 `API-patch-page` 실제 노출 이름과 일치 여부 확인

### 7. 사용자 확인(Human-in-the-loop) 처리

- [o] `slack_post_message` 실행 전 확인 흐름 동작 (LLM 레벨)
- [x] `jira_update_issue` 실행 전 확인 인터럽트 구현
- [x] `API-patch-page` 실행 전 확인 인터럽트 구현
- [o] `create_calendar_block` 실행 전 확인 흐름 동작 (LLM 레벨)
- [o] `delete_calendar_block` 실행 전 확인 흐름 동작 (LLM 레벨)
- [x] LangGraph interrupt() 기반 Human-in-the-loop 구현 (추후)
