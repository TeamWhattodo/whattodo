# WhatToDo — 최종 아키텍처 명세 (Supervisor 패턴)

> 이 문서는 Phase 2 LangGraph 구조에서 Supervisor 패턴으로 전환하는 최종 설계 결정을 기록한다.
> 작성 기준일: 2026-05-29

---

## 1. 설계 배경 및 전환 이유

### Phase 2 정적 그래프의 한계

```
[intent_classifier] → route_by_intent → [briefing | report | action | search]
                                              ↓ (고정 엣지)
                                         [collect] → [output_validator] → END
```

| 문제 | 내용 |
|---|---|
| fetch → report 체인 불가 | briefing(수집)과 report(정리)가 같은 노드에 혼재; 결과를 다음 노드에 전달할 수 없음 |
| 에이전트 간 결과 전달 없음 | SubAgent 결과가 state에만 기록되고, 다음 SubAgent의 입력으로 사용 불가 |
| 조건부 분기 없음 | fetch 실패 시 partial 진행, 결과 품질에 따른 재시도 등 동적 판단 불가 |
| collect_results 실질 동작 안 함 | SubAgent가 `{"text": "..."}` 반환, collect는 `work_items` 기대 → 불일치 |

### 전환 방향: Supervisor 패턴

Orchestrator가 SubAgent를 **tool로 호출**하는 ReAct 루프 구조로 전환한다.
SubAgent는 LangGraph 노드가 아닌 `@tool`로 래핑된 비동기 함수가 된다.

---

## 2. 전체 구조

### 아키텍처 다이어그램

```
사용자
  │
  ▼
┌──────────────────────────────────────────┐
│           Supervisor (Orchestrator)       │
│        LLM Smart · temperature=0         │
│                                          │
│  ReAct 루프:                             │
│    Thought → Tool Call → Observe → ...   │
│                                          │
│  사용 가능한 tool:                        │
│    fetch_agent  report_agent             │
│    search_agent action_agent             │
└──────────┬───────────────────────────────┘
           │ tool call (동적 결정)
     ┌─────┴──────┐
     │            │
  ┌──▼───┐   ┌───▼──┐
  │fetch │   │report│   ← SDK 직접 호출 (Slack 완료, Jira/Notion 예정)
  └──────┘   └──────┘
  ┌──────┐   ┌──────┐
  │search│   │action│   ← 각 팀원 담당
  └──────┘   └──────┘
           │ 결과 반환
           ▼
┌──────────────────────────────────────────┐
│  [Layer 1] Python 실행 전 검증            │
│    write 액션 차단 · 스키마 확인          │
└──────────────────────────────────────────┘
           │
┌──────────────────────────────────────────┐
│  [Layer 2] LLM 출력 품질 검증             │
│    has_write_output=True 일 때만          │
│    is_sufficient 판단 · 최대 2회 재시도   │
└──────────────────────────────────────────┘
           │
         사용자
```

### 기존 구조와 비교

```
# 기존 (Phase 2 정적 그래프)
intent_classifier → [fetch | report | action | search] → collect → validator → END
                    고정 엣지, 에이전트 간 전달 없음

# 신규 (Supervisor)
Supervisor ↔ fetch_agent
     ↕
Supervisor ↔ report_agent(fetched_data=...)   ← fetch 결과 직접 전달
     ↕
Supervisor ↔ search_agent / action_agent
     ↕
최종 응답
```

---

## 3. 복귀 리포트 실행 흐름 (핵심 시나리오)

```
사용자: "3일 쉬고 왔어. 뭐 쌓였는지 정리해줘"
         │
         ▼
Supervisor LLM (temperature=0)
  판단: "복귀 리포트 → fetch 먼저"
         │
         │  tool call: fetch_agent("3일 부재 기간 Slack/Jira/Notion 업무 수집")
         ▼
   fetch_agent 실행
     → slack_list_channels / slack_get_channel_history  (SDK 직접)
     → jira_search                                       (SDK 예정)
     → notion-search / API-get-block-children            (SDK 예정)
         │
         │  결과 반환 → Supervisor로
         ▼
Supervisor LLM
  판단: "fetch 완료, report 호출"
         │
         │  tool call: report_agent(
         │                request="부재 기간 업무 정리",
         │                fetched_data=<fetch 결과>      ← 직접 전달
         │             )
         ▼
   report_agent 실행
         │
         │  결과 반환 → Supervisor로
         ▼
Supervisor LLM
  판단: "리포트 충분함, 종료"
         │
         ▼
   [Layer 2 검증] has_write_output=True → 품질 확인
         │
         ▼
   사용자에게 최종 응답
```

**핵심**: Orchestrator가 매 단계 사이에 개입한다. graph edge 없이 프롬프트 규칙으로 fetch→report 체인이 자동 성립한다.

---

## 4. State 설계

```python
class WhatToDoState(TypedDict):
    messages:         Annotated[list[BaseMessage], add_messages]  # 대화 이력
    user_input:       str
    fetch_results:    Annotated[dict, merge_results]   # NEW: fetch → report 전달 계약
    results:          Annotated[dict, merge_results]   # 최종 출력
    error:            str | None
    retry_count:      int
    has_write_output: Annotated[bool, merge_bool]       # write 액션 발생 여부
    user_preferences: dict
```

> `intent`, `work_items` 제거 — Supervisor가 내부적으로 판단하므로 state 노출 불필요.
> `fetch_results`가 fetch → report 간 계약 키다.

---

## 5. 에이전트 인터페이스 계약

각 팀원이 구현하는 subagent의 public 함수 시그니처.

| 담당 | 함수 | 입력 | 출력 |
|---|---|---|---|
| **fetch** | `run(user_input: str) → tuple[str, dict]` | 자연어 요청 | (요약 텍스트, raw 데이터 dict) |
| **report** | `run(context: str) → tuple[str, list[dict]]` | fetch 데이터 포함 통합 컨텍스트 | (리포트 텍스트, 리포트 파일 목록) |
| **search** | `run(query: str) → tuple[str, bool]` | 검색 쿼리 | (결과 텍스트, write 여부) |
| **action** | `run(request: str) → tuple[str, bool]` | 자연어 요청 | (처리 결과 텍스트, write 여부) |

`agent_tools.py`(orchestrator 담당)가 이 함수들을 `@tool`로 래핑한다.
각 담당자는 내부 구현만 책임지고 시그니처만 지키면 된다.

---

## 6. 핵심 파일 구조

```
backend/agents/
  orchestrator.py           ← build_supervisor() 추가 (기존 코드 유지)
  graph.py                  ← build_supervisor 호출로 교체 (단순화)
  llm_client.py             ← temperature 파라미터 추가
  subagents/
    agent_tools.py          ← NEW: subagent를 @tool로 래핑 (orchestrator 담당)
    fetch_agent.py          ← briefing_agent.py 리네임 + run() 공개
    report_agent.py         ← run() 공개
    search_agent.py         ← run() 공개
    action_agent.py         ← run() 공개
    briefing_agent.py       ← legacy (제거 예정)
```

**변경 없는 파일**:
```
backend/tools/*.py          ← 전혀 수정 없음 (모든 도구 구현체)
backend/agents/tools_registry.py  ← 수정 없음
backend/agents/sessions.py        ← 수정 없음
backend/mcp_client.py             ← 수정 없음
```

---

## 7. Validation Layer (2단계)

상용 서비스 표준 구조를 따른다. LLM 판단이 아닌 **Python 코드**로 강제하는 부분과 LLM 검증을 명확히 분리한다.

### Layer 1 — Python 실행 전 검증 (신규)

```python
# agent_tools.py 내 before_tool_call 훅
REQUIRES_CONFIRMATION = {
    "slack_post_message",
    "jira_update_issue",
    "API-patch-page",
    "create_calendar_block",
}

def guard(tool_name: str) -> None:
    """write 액션은 Python 코드로 차단 — LLM 프롬프트 의존 금지."""
    if tool_name in REQUIRES_CONFIRMATION:
        raise RequiresConfirmationError(tool_name)
```

- 스키마 검증 (필수 파라미터 누락 체크)
- write/destructive 액션 차단 → 사용자 확인 요청
- 루프 제어: `recursion_limit=50` 하드 제한 (코드로 강제)

### Layer 2 — LLM 출력 품질 검증 (기존 output_validator 유지)

```python
# has_write_output=True 일 때만 실행 — 비용 최적화
if state.get("has_write_output"):
    verdict = llm.invoke(VERIFY_PROMPT + result_text)
    if not verdict["is_sufficient"]:
        # feedback 반영 후 재생성 (max 2회)
        regenerate(verdict["feedback"])
```

- write_report / write_draft 결과에만 적용
- `is_sufficient=false` → 피드백 포함 재생성 최대 2회
- 단순 조회(search) 결과는 생략 — 토큰 비용 절약

---

## 8. SDK 전환 계획

MCP stdio 프로세스 불안정성과 출력 비정규화가 Slack 비결정적 동작의 근본 원인이었다.
SDK 직접 호출로 전환해 출력 정규화와 안정성을 확보한다.

| 서비스 | 현재 | 전환 후 | 상태 |
|---|---|---|---|
| Slack | MCP (mcp-slack) | `slack_sdk` WebClient | ✅ 완료 (`slack_fetch` 브랜치) |
| Jira | MCP (mcp-atlassian) | `atlassian-python-api` | 🔶 예정 |
| Notion | MCP (notion MCP) | `notion-client` | 🔶 예정 |
| GitHub | MCP | MCP 유지 또는 SDK | 선택 사항 |

**Slack SDK 추가 개선 사항** (`slack_fetch` 브랜치):

```python
# 1. 모듈 레벨 싱글톤 (현재 매 호출마다 new WebClient)
_client = WebClient(token=settings.slack_bot_token)

# 2. 출력 정규화 — 필요 필드만 반환
def _normalize_message(m: dict) -> dict:
    return {"ts": m["ts"], "user": m.get("user",""), "text": m.get("text","")}

# 3. slack_search_messages 제거 또는 user token 분기
# search.messages scope는 bot token 불가 → 항상 missing_scope 실패
```

---

## 9. Supervisor 패턴에서 가능해지는 기능

| 기능 | 정적 그래프 | Supervisor |
|---|---|---|
| fetch → report 자동 체인 | graph edge 수동 추가 필요 | 프롬프트 규칙으로 자동 |
| Slack 메시지 → Jira 등록 | fetch+action edge 없어 불가 | fetch → action(context=...) 자연스럽게 가능 |
| 리포트 결과 품질 미흡 시 재수집 | output_validator 고정 로직만 | Orchestrator가 판단 후 fetch 재호출 |
| 병렬 tool 호출 | Send API 수동 작성 필요 | LLM이 자동으로 parallel tool call |
| 대화 맥락 기반 follow-up | user_input 문자열만 전달 | messages 히스토리 전체 공유 |
| 3개 이상 에이전트 체인 | graph 수동 수정 필요 | 프롬프트만으로 가능 |
| 수집 실패 시 부분 결과 진행 | 불가 | Orchestrator가 실패 감지 후 대안 실행 |
| write 전 사용자 확인 요청 | Phase 3 interrupt() 필요 | Layer 1에서 즉시 처리 |

---

## 10. 팀 분업

| 담당 | 파일 | 주요 작업 |
|---|---|---|
| orchestrator | `orchestrator.py`, `graph.py`, `agent_tools.py` | build_supervisor() 구현, subagent @tool 래핑, Layer 1 guard |
| fetch | `fetch_agent.py` (briefing_agent 리네임) | Slack SDK 개선, Jira/Notion SDK 전환, run() 공개 |
| report | `report_agent.py` | fetched_data context 수신 처리, run() 공개 |
| search | `search_agent.py` | Notion SDK 전환, run() 공개 |
| action | `action_agent.py` | Jira SDK 전환, run() 공개 |

**인터페이스 합의 후 독립 작업 가능.** `agent_tools.py`는 orchestrator 담당자가 작성하고, 각자는 `run()` 시그니처만 지키면 된다.

---

## 11. 구현 우선순위

```
1. [orchestrator] WhatToDoState에 fetch_results 추가
   → 다른 모든 작업의 전제 조건

2. [orchestrator] build_supervisor() + agent_tools.py 뼈대
   → 팀원 개별 run() 연결 가능해짐

3. [fetch] fetch_agent.py 리네임 + run() 공개
   → Slack SDK 싱글톤·정규화 개선 포함

4. [report/search/action] 각자 run() 공개
   → 내부 로직 변경 없이 함수명 export만

5. [fetch] Jira SDK 전환 (atlassian-python-api)

6. [fetch/search] Notion SDK 전환 (notion-client)

7. [orchestrator] Layer 1 Python guard 구현
   → write 액션 확인 요청 흐름

8. [orchestrator] llm_client.py temperature 파라미터
   → Supervisor temperature=0 적용
```

---

## 12. 핵심 설계 원칙 (변경 없음)

```
Orchestrator  → "무엇을, 어떤 순서로" 동적 결정 (ReAct 루프)
SubAgent      → "어떻게 할 건지" 자율 결정 (도메인 내 tool_use)
Tool          → "실제로 한 가지 일" 실행 (순수 함수)
```

- SubAgent 시스템 프롬프트는 순서(sequence)가 아닌 제약(constraint)만 명시
- write/destructive 액션은 Python 코드로 차단 — 프롬프트 의존 금지
- recursion_limit은 코드로 하드 제한 (50) — 무한루프 90% 차단
- Orchestrator는 `temperature=0` — 라우팅 결정 결정론적 유지
- tools는 전혀 수정하지 않는다 — 워크플로우 레이어만 교체
