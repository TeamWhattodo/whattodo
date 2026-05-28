# WhatToDo — 현재 진행 상황 및 미결 사항

> 최종 업데이트: 2026-05-28  
> 브랜치: `feat/langgraph-core`

---

## 1. 완료된 작업

### LangGraph 기반 멀티에이전트 구조 전환 (Phase 2)

| 항목 | 상태 |
|---|---|
| LangGraph StateGraph + 노드 구성 | ✅ |
| WhatToDoState TypedDict 정의 | ✅ |
| intent_classifier (Smart LLM) | ✅ |
| route_by_intent — 단일/복합 의도 분기 | ✅ |
| collect_results 노드 | ✅ |
| output_validator 노드 (최대 2회 재시도) | ✅ |
| MemorySaver 체크포인터 (멀티턴 대화 이력) | ✅ |
| general_chat 노드 | ✅ |

### SubAgent 구현

| 에이전트 | 상태 | 할당 툴 |
|---|---|---|
| BriefingAgent | ✅ | slack_list_channels, slack_get_channel_history, jira_search, API-post-search, API-get-block-children |
| ReportAgent | ✅ | fetch_uploaded_file, parse_billing_data, parse_receipt, compute_daily_stats, compute_kpi, write_report |
| ActionAgent | ✅ | search_past_items, write_draft, update_item_status + slack_get_thread_replies, slack_post_message, jira_update_issue, API-patch-page |
| SearchAgent | ✅ | search_past_items, search_company_docs + slack_search_messages, jira_search, API-post-search, API-get-block-children |

- 툴 허용 방식: prefix 기반 → **exact name 매칭**으로 변경 (에이전트 컨텍스트 최소화)

### MCP 서버 연결

| 플랫폼 | 서버 | 출처 |
|---|---|---|
| Slack | `@modelcontextprotocol/server-slack` | MCP 공식 (Anthropic) |
| Jira | `mcp-atlassian` | 커뮤니티 |
| Notion | `@notionhq/notion-mcp-server` | Notion 공식 |
| GitHub | `@modelcontextprotocol/server-github` | MCP 공식 (Anthropic) |

### 기타

| 항목 | 상태 |
|---|---|
| LangSmith 트레이싱 환경변수 추가 (`.env.example`) | ✅ |
| `app.py`에 `load_dotenv()` 추가 | ✅ |
| MCP 서버 이중 기동 방지 (`_alive_clients` GC 방지) | ✅ |
| BriefingAgent 시스템 프롬프트 — 수집 소스 자율 선택 | ✅ |
| BriefingAgent recursion_limit 15 → 30 | ✅ |

---

## 2. 미결 사항 (Critical → Potential)

### 🔴 Critical — 즉시 해결 필요

#### C1. `InvalidUpdateError` — 병렬 노드 reducer 누락

**재현 조건**: 복합 의도 ("report,search" 등) 발생 시  
**원인**: `route_by_intent`가 `Send` 리스트를 반환해 서브에이전트가 병렬 실행되는데, 각 노드가 `{**state, ...}` 로 `user_input` 등 reducer 없는 키를 모두 반환

**수정 필요 파일**:
- `backend/agents/orchestrator.py` — WhatToDoState에 reducer 추가
- `backend/agents/subagents/*.py` — 4개 노드 반환값을 변경 키만 반환하도록 수정

```python
# 수정 방향 (Option A — 권장)
class WhatToDoState(TypedDict):
    results: Annotated[dict, lambda a, b: {**a, **b}]       # merge reducer
    has_write_output: Annotated[bool, lambda a, b: a or b]  # or reducer
    # user_input, intent 등은 노드에서 반환하지 않으면 됨

# 각 서브에이전트 노드 반환값
return {
    "results": {"briefing": {"text": text}},
    "has_write_output": has_write,
}
# {**state, ...} 제거
```

#### C2. 미구현 툴 참조

| 툴 | 참조 에이전트 | 상태 |
|---|---|---|
| `get_item_thread` | ActionAgent, SearchAgent | ❌ tools_registry.py 미구현 |
| `create_calendar_block` | ActionAgent | ❌ tools_registry.py 미구현 |

#### C3. `collect_results` 데이터 포맷 불일치

서브에이전트는 `{"text": "..."}` 형태로 반환하지만 `collect_results`는 `{"work_items": [...]}` 구조를 기대한다 → `work_items` 항상 빈 리스트.

---

### 🟠 High — 기능 저하

| 항목 | 설명 |
|---|---|
| **H1. 대화 맥락 미전달** | 서브에이전트에 `user_input` 문자열만 전달, `messages` 이력 없음 → follow-up 불가 |
| **H2. SearchAgent RAG 우선 문제** | Notion 내용 조회 요청이 `search_company_docs`(RAG)로 빠짐. 시스템 프롬프트 수정 필요 |
| **H3. score_urgency/classify_items 미연결** | tools_registry에 있으나 어떤 에이전트에도 할당 안 됨 |
| **H4. MemorySaver — 재시작 시 이력 소실** | 앱 재시작마다 대화 이력 초기화 → SqliteSaver 전환 필요 |

---

### ⚪ Potential — 장기 검토

| 항목 | 설명 |
|---|---|
| 스트리밍 미지원 | `invoke()` 기반, 긴 MCP 호출 중 사용자 피드백 없음 |
| 단일 `_bg_loop` | 병렬 에이전트가 같은 이벤트 루프에 직렬 대기 → 실질적 병렬 효과 없음 |
| Tool 이름 가독성 | Notion MCP 툴명이 `API-post-search` 등 REST 동사 기반 → 에이전트 혼선 |
| Jira MCP 공식 전환 | `mcp-atlassian`(커뮤니티) → `@atlassian/mcp`(공식) 교체 검토 |

---

## 3. 아키텍처 논의 사항 (미확정)

### 에이전트 구조 개편 방향

현재 BriefingAgent가 fetch + summarize를 혼합 처리 중. 논의된 개편안:

**현재 (4 에이전트)**
```
briefing → fetch + summarize 혼합
report   → 파일 파싱 + 리포트 생성
action   → 쓰기·업데이트
search   → RAG + 실시간 조회 혼합
```

**논의 중 (3 에이전트)**
```
search  → 데이터 수집(fetch) + 특정 정보 조회 통합
          - fetch 모드: 전체 소스 수집 (브리핑용)
          - search 모드: 특정 키워드 조회
report  → 수집 데이터 정리·요약 (브리핑 요약 + 정식 리포트)
action  → 쓰기·업데이트·발송

라우팅:
  briefing → search → report (순차 파이프라인)
  report   → report
  search   → search
  action   → action
```

**추가 검토 중 (4 에이전트, 역할 명확화)**
```
fetch  → 실시간 소스 수집 전담 (Slack/Jira/Notion MCP)
search → 정적 문서 조회 전담 (RAG)
report → 데이터 정리·요약
action → 쓰기·업데이트
```

→ **확정 필요**: 동적(MCP) vs 정적(RAG) 검색을 분리할지 여부  
→ **선행 조건**: C1 reducer 수정 + State 재설계와 묶어서 진행

### Tool 개선 방향

- **Tool 이름 재정의**: MCP 툴을 `StructuredTool`로 감싸 의미 있는 이름 부여  
  예) `API-post-search` → `notion_search_pages`
- **Output 정규화**: `slack_get_channel_history` 응답에서 필요 필드만 추려 반환
- **Tool Selector 노드**: 실행 전 필요 툴 목록을 LLM이 먼저 선택하는 노드 분리

---

## 4. 다음 작업 순서 (권장)

```
1. [즉시] C1 reducer 수정 + 서브에이전트 반환값 정규화
2. [즉시] C2 미구현 툴 구현 (get_item_thread, create_calendar_block)
3. [단기] 에이전트 구조 개편 확정 후 State 재설계
4. [단기] SearchAgent 프롬프트 — Notion MCP vs RAG 분기 명확화
5. [단기] collect_results 데이터 계약 통일
6. [중기] SqliteSaver 전환 (대화 영속성)
7. [중기] Tool 이름 재정의 + Output 정규화
```
