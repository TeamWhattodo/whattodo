# WhatToDo — AI 멀티에이전트 업무 보조 시스템 발표 자료

## 프로젝트 개요

WhatToDo는 직장인의 업무 과부하 문제를 AI 에이전트가 해결하는 서비스입니다.

휴가를 다녀온 다음 날을 상상해보세요. 이메일 47통, 슬랙 멘션 213개, Jira 알림 8건. 어디서부터 봐야 할지 막막한 채 오전이 지나갑니다. WhatToDo는 이 문제를 "앱 하나 열면 30초 안에 긴급한 것 3건부터 알려준다"로 바꾸는 것이 목표입니다.

---

## 팀 구성과 역할 분담

6인 팀으로 진행된 프로젝트입니다. 처음부터 역할을 명확하게 나눴습니다.

- **팀장(오케스트레이터 + 프론트엔드)**: 에이전트 핵심 루프, LLM 클라이언트, UI
- **Fetch 담당**: Gmail, Slack, Calendar 커넥터, OAuth 인증
- **Score/Classify 담당**: 긴급도 계산 엔진, 항목 분류
- **Write 담당**: 보고서 생성, 답장 초안, PDF 출력
- **Action/Search 담당**: 상태 관리, 항목 검색, DB CRUD
- **Compute/Data 담당**: 통계 집계, 정산 파싱, 스케줄러

팀원마다 독립적으로 개발하면서도 `WorkItem` 스키마 하나로 연결되는 구조를 프로젝트 초반에 합의로 확정했습니다. 이 결정이 이후 병렬 개발의 기반이 됐습니다.

---

## 개발 여정: 어떻게 여기까지 왔나

### 1단계 — 계획과 명세

코드를 쓰기 전에 설계를 먼저 다졌습니다.

핵심 결정은 두 가지였습니다. 첫째, **Tool Registry 패턴**입니다. 기능을 추가할 때마다 에이전트 코드를 건드리지 않고 tool만 등록하면 에이전트가 자동으로 활용합니다. 둘째, **단계별 전환 전략**입니다. No-agent 파이프라인에서 시작해 단일 에이전트, 멀티에이전트 순서로 점진적으로 전환합니다. 무리하게 처음부터 복잡한 구조로 가지 않았습니다.

`WorkItem`이라는 공통 데이터 모델을 먼저 확정했습니다. Gmail에서 오든 Slack에서 오든 Jira에서 오든, 모든 업무 항목이 동일한 구조를 갖습니다. id, source, summary, urgency_level, action_type, status. 이 합의 덕분에 각 팀원이 이후 독립적으로 작업할 수 있었습니다.

### 2단계 — No-Agent: 함수 파이프라인

에이전트 없이 Python 함수들을 순서대로 직접 호출하는 것에서 시작했습니다.

```
fetch_emails() → score_urgency() → classify_items() → write_report()
```

LLM이 전혀 없습니다. mock 데이터를 넣으면 각 함수가 데이터를 변환해 다음 함수에 넘깁니다. 목적은 파이프라인이 올바르게 동작하는지 확인하는 것이었습니다. 이 단계에서 `WorkItem` 스키마가 실제로 팀 전체를 연결하는지 검증했습니다.

이 접근의 가치: 에이전트가 잘못 동작할 때 "LLM 판단 문제인가, tool 로직 문제인가"를 분리할 수 있습니다. 파이프라인이 먼저 정확하게 동작해야 에이전트를 올릴 수 있습니다.

### 3단계 — 워크플로우: LLM 직접 호출

실데이터를 연결하고 LLM을 `messages.create`로 직접 호출했습니다. tool_use가 아닙니다.

```
실데이터 수집 → LLM에게 직접 질문 → 응답 파싱 → 다음 단계로 전달
```

이 단계의 목적은 LLM 응답 형식을 파악하는 것이었습니다. "이 항목들을 분류해줘"라고 보내면 어떤 포맷으로 돌아오는가, 파싱이 어떻게 깨지는가. tool_use 루프를 만들기 전에 LLM과의 인터페이스를 먼저 이해했습니다.

이 시기에 RAG 시스템도 구축했습니다. 사내 규정 문서를 PDF로 업로드하면 ChromaDB에 임베딩하고, 에이전트가 "출장 교통비 한도 얼마야?"라고 물으면 즉시 검색해서 답합니다. 임베딩 모델은 `jhgan/ko-sroberta-multitask`, 한국어 특화 무료 모델을 선택했습니다.

멀티턴 세션 관리도 이 시기에 추가됐습니다. 대화를 새로 시작해도 이전 맥락이 유지되는 세션 영속성. 영수증 이미지 처리, Slack/Jira/Notion MCP 연결도 같은 시기에 진행됐습니다.

### 4단계 — 단일 에이전트: tool_use 루프

LLM이 tool을 스스로 선택하는 구조로 전환했습니다. `WorkAssistantAgent`가 TOOL_REGISTRY에 등록된 모든 tool을 보고 요청에 맞는 tool을 자율적으로 선택합니다.

```
사용자 명령
    ↓
WorkAssistantAgent (LLM Smart + TOOL_REGISTRY)
    Thought → Act(tool 선택) → Observe → 반복
    ↓
최종 답변
```

핵심 변화는 "코드가 순서를 정하는 것"에서 "LLM이 순서를 정하는 것"으로의 전환입니다. "정산 리포트 작성해줘"라고 하면 에이전트가 스스로 fetch → parse → compute → write_report 순서를 결정합니다.

Google OAuth 연결로 Gmail과 Calendar 실데이터가 들어오기 시작했습니다. 보고서 PDF 생성(일일/주간/월간), 맞춤법 검사 tool도 이 시기에 추가됐습니다.

### 5단계 — 정적 멀티에이전트: LangGraph StateGraph

tool이 15개를 넘어서자 단일 에이전트의 tool 선택 정확도가 낮아졌습니다. 역할을 나눠야 할 시점이었습니다.

LangGraph의 StateGraph로 Intent Classifier + 4개 SubAgent 구조를 만들었습니다.

```
사용자 명령
    ↓
intent_classifier (의도 파악)
    ↓ route_by_intent
BriefingAgent | ReportAgent | ActionAgent | SearchAgent
    ↓
collect_results → output_validator → 최종 답변
```

각 SubAgent는 자신의 도메인 tool만 갖습니다. BriefingAgent는 fetch/score/classify, ReportAgent는 write/compute, ActionAgent는 update/draft, SearchAgent는 search/rag.

이 구조가 동작하면서 세 가지 문제가 드러났습니다. fetch 결과를 report에 전달하려면 graph edge를 수동으로 추가해야 했습니다. SubAgent 결과가 다음 SubAgent 입력으로 쓰이지 않았습니다. 수집 실패 시 부분 진행 같은 동적 판단을 표현할 수 없었습니다.

Action Agent가 이 시기에 완성됐습니다. Slack 발송, Jira 업데이트, Notion 수정, Calendar 이벤트 생성/삭제까지 전 서비스 CRUD. Slack은 MCP stdio 불안정성 때문에 SDK 직접 호출로 전환했습니다.

### 6단계 — 동적 멀티에이전트: Supervisor 패턴 (ReAct)

가장 중요한 아키텍처 결정이 내려집니다. **Supervisor 패턴으로 전환**입니다.

---

## 핵심 아키텍처 결정: 왜 Supervisor 패턴인가

### 기존 정적 그래프의 한계

LangGraph의 StateGraph는 노드와 엣지를 미리 정의합니다. 이 구조에서 세 가지 문제가 발견됐습니다.

첫째, **fetch → report 체인이 불가능**했습니다. Slack 메시지를 수집(fetch)한 결과를 보고서 생성(report) 노드에 전달하려면 graph edge를 수동으로 추가해야 합니다. 요구사항이 바뀔 때마다 그래프 구조를 수정해야 했습니다.

둘째, **에이전트 간 결과 전달이 없었습니다**. SubAgent가 `{"text": "..."}` 형태로 반환해도 다음 SubAgent의 입력으로 쓰이지 않았습니다. 각자의 결과가 state에만 기록될 뿐이었습니다.

셋째, **동적 판단이 불가능**했습니다. fetch 실패 시 부분 진행, 결과 품질이 낮을 때 재수집 같은 판단을 graph 구조로는 표현하기 어렵습니다.

### Supervisor 패턴의 해법

Orchestrator가 SubAgent를 **tool로 호출**하는 ReAct 루프 구조입니다.

```
사용자
  ↓
Supervisor (Smart LLM, temperature=0)
  ReAct 루프: Thought → Tool Call → Observe → ...
  ↓
fetch_agent / briefing_agent / report_agent / search_agent / action_agent
  ↓
Python tools (Gmail, Slack, Jira, Notion, Calendar...)
```

이 구조에서 Orchestrator는 매 단계 사이에 개입합니다. "fetch 결과를 report에 넘겨라"는 graph edge가 아니라 프롬프트 규칙으로 자동 성립합니다. Supervisor가 판단해서 필요하면 재수집하고, 필요하면 병렬로 tool을 호출합니다.

### HitL (Human-in-the-Loop)

"이메일 발송", "Slack 메시지 전송", "Jira 이슈 수정" 같은 파괴적 액션은 사용자 확인 없이 실행되면 안 됩니다. LangGraph의 `interrupt()` 메커니즘으로 구현했습니다.

에이전트가 파괴적 액션을 취하려 하면 실행을 중단하고 사용자에게 확인을 요청합니다. "이 내용으로 박팀장에게 발송할까요?"라고 물어보고 승인을 받으면 그 시점부터 다시 실행합니다. 중요한 것은 이 체크가 **Python 코드로 강제**된다는 점입니다. 프롬프트 지시만으로는 충분하지 않습니다.

---

## 기술 스택의 진화

### 데이터 저장소: TinyDB → PostgreSQL + pgvector

처음에는 파일 기반 TinyDB로 시작했습니다. 개발 속도를 위한 선택이었습니다.

PostgreSQL 마이그레이션이 필요해진 이유는 두 가지입니다. 첫째, LangGraph의 대화 이력 영속성을 위해 PostgresSaver가 필요했습니다. MemorySaver는 서버 재시작 시 모든 대화 이력이 날아갑니다. 둘째, 벡터 검색을 위해 pgvector 확장이 필요했습니다.

ChromaDB에서 pgvector로 전환하면서 얻은 것: 별도 벡터 DB 프로세스 없이 PostgreSQL 하나로 관계형 데이터와 벡터 검색을 모두 처리합니다. 인프라가 단순해집니다.

### 벡터 검색: 사내 규정 RAG

회사 규정 PDF를 업로드하면 pgvector에 임베딩됩니다. 에이전트가 규정 관련 질문을 받으면 이 벡터 DB를 검색해 관련 청크를 찾아 답변합니다.

"출장 교통비 한도 얼마야?" → 벡터 검색 → "3.2절에 따르면 1일 5만원입니다"

규정이 바뀌면 PDF만 교체하면 됩니다. 에이전트 코드를 수정할 필요가 없습니다.

### 프론트엔드: Streamlit → React + Vite

초기 기획에는 Streamlit으로 빠르게 UI를 만들기로 했습니다. 실제로 구현하다 보니 실시간 스트리밍과 복잡한 인터랙션이 Streamlit으로는 한계가 있었습니다.

React 19 + Vite로 전환하면서 SSE(Server-Sent Events) 스트리밍을 구현했습니다. LLM이 답변을 생성하는 동안 글자가 실시간으로 흘러나오는 경험이 가능해졌습니다.

### 스트리밍 아키텍처

백엔드 FastAPI에서 SSE로 이벤트를 전송합니다. 이벤트 유형은 세 가지입니다.

- `delta`: LLM이 생성하는 텍스트 조각
- `structured`: 카드 데이터, 파일 다운로드 링크 등 구조화 데이터
- `done`: 스트림 종료

프론트엔드는 이 이벤트를 실시간으로 수신해 렌더링합니다. 사용자는 LLM이 생각하는 동안 기다리지 않고 답변이 만들어지는 것을 봅니다.

---

## 주요 기능 상세

### 복귀 브리핑

"3일 쉬고 왔어. 뭐 쌓였는지 정리해줘"

에이전트가 Gmail, Slack, Calendar, Jira, Notion에서 항목을 수집합니다. 긴급도 엔진이 마감 시간, 발신자 중요도, 반복 연락 횟수를 조합해 1~5점을 계산합니다. 결과를 카드 형태로 보여줍니다.

- 🔴 지금 당장 (3건): 계약서 서명, 배포 승인, 예산 승인
- 🟡 오늘 안에 (7건): 주간 회의 준비 외
- ⚪ FYI (180건): 접혀 있음

중요한 점은 긴급도가 AI의 주관적 판단이 아니라 **정량 지표 기반**이라는 것입니다. "마감이 언제까지인가", "이 사람이 몇 번 연락했는가" 같은 객관적 신호를 조합합니다.

### 답장 초안 작성

"박팀장 DM 답장 초안 써줘"

에이전트가 Slack에서 해당 스레드 전체를 가져와 맥락을 파악한 뒤 초안을 생성합니다. formal/casual 톤을 선택할 수 있습니다. 초안은 확인 후 직접 복사해서 사용합니다. 에이전트가 대신 발송하려면 명시적 승인이 필요합니다.

### 경비 정산

영수증 이미지나 텍스트를 올리면 항목(날짜, 가맹점, 금액, 카테고리)을 자동 추출합니다. 사내 규정 RAG와 연동하면 "식대 3만2천원이 규정 한도 3만원을 초과합니다"까지 자동으로 검증합니다. 최종 정산서는 Excel로 내보낼 수 있습니다.

스캔 PDF도 Vision OCR로 처리합니다.

### 사내 규정 검색

규정집 PDF를 업로드해두면 자연어 질문으로 즉시 조회합니다. RAG 방식이므로 키워드 검색이 아닌 의미 기반 검색입니다. "해외 출장 일비 규정" 같이 묻고 싶어도 정확한 키워드를 몰라도 됩니다.

### 보고서 자동 생성

일일, 주간, 월간 업무보고서를 공문서 형식 PDF로 생성합니다. "이번 주 보고서 작성해줘"라고 하면 이번 주 완료된 항목을 조회해 자동으로 채웁니다.

---

## 성능 평가 시스템

TheAgentCompany 방법론을 참고해 에이전트 평가 파이프라인을 직접 구축했습니다.

평가 지표는 네 가지입니다.

- **Success Rate**: 시나리오의 모든 체크포인트를 통과하는 비율
- **Partial Score**: 완전 성공과 부분 성공을 함께 반영하는 점수
- **Tool Call Accuracy**: 올바른 tool을 올바른 순서로 호출했는지
- **Hallucination Rate**: LLM이 없는 정보를 만들어냈는지

이 평가 시스템으로 OpenAI와 Anthropic 모델을 직접 비교했습니다. gpt-4o, gpt-4o-mini, claude-sonnet-4-6를 동일 시나리오에서 각 5회씩 돌려 평균을 냈습니다. 모델 선택이 성능에 얼마나 영향을 주는지 데이터로 확인했습니다.

```bash
# 모델 비교 실행
uv run python -m eval.compare --runs 5
```

---

## 인증과 다중 사용자

처음에는 사용자 인증 없이 단일 사용자 환경으로 시작했습니다. 팀 프로젝트 특성상 빠른 데모가 우선이었습니다.

다중 사용자 지원은 이후 추가됐습니다. JWT 기반 인증, Refresh Token 관리, OAuth 토큰 AES-256 암호화. 사용자마다 자신의 Gmail, Slack, Jira 연동을 독립적으로 설정합니다.

중요한 보안 원칙: 외부 서비스 OAuth 토큰은 암호화해서 저장합니다. 메시지 원문은 처리 후 요약본만 보관합니다. 발송/수정 액션은 반드시 사용자 확인을 받습니다.

---

## Docker와 배포 구조

전체 시스템을 Docker Compose 하나로 올릴 수 있습니다.

```
db       (pgvector/pgvector:pg17) — PostgreSQL + 벡터 검색
backend  (FastAPI + LangGraph)    — AI 에이전트, API 서버
frontend (React + Vite)          — 사용자 인터페이스
```

개발 중에는 hot reload가 활성화됩니다. 코드를 수정하면 서버 재시작 없이 바로 반영됩니다. 볼륨 마운트로 소스 코드를 컨테이너 내부와 동기화합니다.

---

## 개발하면서 배운 것들

### 1. 인터페이스 합의가 병렬 개발의 핵심이다

6인이 동시에 개발하면서 가장 중요했던 것은 초기에 합의한 `WorkItem` 스키마입니다. 이 공통 계약 덕분에 Fetch 담당자가 Gmail 커넥터를 만드는 동안 Write 담당자는 mock 데이터로 보고서 생성을 개발할 수 있었습니다.

### 2. MCP보다 SDK 직접 호출이 안정적이다

Slack MCP stdio 프로세스는 Windows에서 크래시가 잦았고, 출력 형식이 비결정적이었습니다. SDK 직접 호출로 전환하자 안정성이 크게 개선됐습니다. 외부 서비스 연결에 MCP를 쓰는 것이 항상 옳은 선택은 아닙니다.

### 3. 프롬프트보다 코드로 강제하라

파괴적 액션(이메일 발송, 데이터 삭제)을 프롬프트 지시로만 막으려 하면 LLM이 지시를 무시할 수 있습니다. Python 코드로 실행 전에 차단하는 것이 훨씬 안전합니다.

### 4. 정적 그래프의 한계를 일찍 발견했다

Phase 2에서 LangGraph StateGraph로 전환했다가 Supervisor 패턴으로 다시 전환한 것이 돌아보면 예측 가능한 결과였습니다. 업무 흐름이 동적으로 결정돼야 하는 상황에서 정적 그래프는 확장이 어렵습니다. Supervisor 패턴이 처음부터 더 맞는 선택이었을 수 있습니다.

### 5. 평가 없이 개선할 수 없다

에이전트 품질을 개선하려면 측정이 먼저입니다. "왠지 더 잘 되는 것 같다"는 느낌이 아니라 Success Rate, Tool Call Accuracy 같은 정량 지표로 확인해야 합니다. 평가 시스템을 일찍 만든 것이 이후 모델 비교와 프롬프트 튜닝에 큰 도움이 됐습니다.

---

## 현재 상태와 앞으로

### 완성된 것들

- 복귀 브리핑, 답장 초안, 경비 정산, 보고서 생성, 사내 규정 검색
- Gmail, Google Calendar, Slack, Jira, Notion 연동
- LangGraph Supervisor 패턴 + HitL
- SSE 스트리밍 실시간 UI
- 다중 사용자 인증 및 토큰 암호화
- pgvector 기반 벡터 검색
- Docker Compose 배포 구성
- 모델 비교 평가 시스템

### 앞으로 할 것들

- EC2 프로덕션 배포 (nginx + HTTPS)
- 모바일 PWA
- 팀 대시보드 (팀 전체 업무 현황)
- 주간 KPI 자동 리포트 (APScheduler 스케줄링)
- 5-신호 긴급도 엔진 고도화 (사용 패턴 기반 개인화)

---

## 마무리

WhatToDo는 3주 만에 기획부터 멀티에이전트 시스템까지 구현한 프로젝트입니다.

핵심은 "에이전트가 도구를 선택한다"는 설계 원칙입니다. 새 기능이 필요하면 tool 하나를 추가하고 등록하면 됩니다. 에이전트 로직을 건드릴 필요가 없습니다. 이 원칙 덕분에 6인 팀이 충돌 없이 빠르게 병렬로 기능을 쌓을 수 있었습니다.

AI 에이전트는 "뭔가 신기한 것"이 아닙니다. 사람이 반복적으로 하는 업무를 정확하게 식별하고, 그것을 tool로 분해하고, LLM에게 언제 어떤 tool을 쓸지 판단하게 하는 것입니다. WhatToDo는 그 과정을 직장인의 일상 업무에 적용한 프로젝트입니다.
