# WhatToDo — 직장인 업무 복귀 어시스턴트 기획서

## 1. 서비스 개요

**WhatToDo**는 여러 업무 채널(이메일·슬랙·캘린더·Jira 등)에 흩어진 알림과 태스크를 AI 에이전트가 자동으로 수집·분류·우선순위화해, **"지금 무엇을 해야 하는가"를 매일 제시**하고 **"오늘 무엇을 했는가"를 결산**해주는 AI 업무 인텔리전스 서비스다.

출근·복귀 시 쌓인 항목을 브리핑하는 것을 출발점으로, 체크리스트 위젯을 통한 일상적 업무 관리, 일간 결산, 주간 KPI 리포트, 사내 규정 반영까지 확장된다.

| 항목 | 내용 |
|---|---|
| 서비스명 | WhatToDo |
| 타깃 사용자 | 이메일·슬랙·Jira 등 여러 도구를 동시에 사용하는 직장인 |
| 핵심 가치 | 업무가 쌓이기 전에 파악하고, 하루가 끝나면 무엇을 했는지 안다 |
| 서비스 형태 | Streamlit 체크리스트 앱 (MVP) → 슬랙 봇 (Phase 2) → 모바일 PWA (Phase 3) |

### 핵심 기능 한눈에 보기

| 기능 | 설명 | 제공 시점 |
|---|---|---|
| 복귀 브리핑 | 부재 기간 쌓인 항목을 수집·분류해 우선순위 카드로 제시 | MVP |
| 체크리스트 위젯 | 긴급도 순 카드 목록, 완료 체크, 섹션별 정리 | MVP |
| 일간 작업 결산 | 완료 항목·이월 항목·처리 통계 자동 집계 | Phase 2 |
| 주간 KPI 리포트 | 완료율·응답 시간·채널별 부하 등 개인 생산성 지표 | Phase 3 |
| 사내 규정 엔진 | 회사별 보고 체계·승인 규정을 에이전트 동작에 반영 | Phase 3 |

---

## 2. 문제 정의

```
[현재 상황]
- 하루 쉬고 출근하면 이메일 수십 통, 슬랙 멘션 수백 개
- 어디서부터 봐야 하는지 몰라 중요한 건 놓치고 급하지 않은 것에 시간 낭비
- 마감이 지난 태스크를 뒤늦게 발견해 신뢰 손상

[해결하려는 것]
- 모든 채널을 한 곳에서 집계
- AI가 중요도·긴급도·담당자를 자동 분류
- "지금 당장 해야 할 일 TOP 5"를 즉시 제시
```

---

## 3. 핵심 기능 (MVP)

### 3-1. 멀티소스 수집
| 소스 | 수집 대상 |
|---|---|
| Gmail / Outlook | 읽지 않은 이메일, 미수락 캘린더 초대 |
| Slack | 멘션(@me), DM, 리마인더 |
| Google Calendar | 오늘~3일 내 일정, 마감 임박 이벤트 |
| Jira / Linear | 나에게 할당된 미완료 이슈, due date 초과 이슈 |
| Notion / Confluence | 나를 태그한 댓글, 승인 대기 문서 |

### 3-2. 분류 및 우선순위 결정

**긴급도 — 정량 엔진 (LLM 미사용)**

5개 신호를 각각 0~1로 정규화한 후 가중합으로 계산. 동일 항목은 항상 동일 점수가 나오고 근거를 사용자에게 설명할 수 있다.

| 신호 | 가중치 | 측정 방법 |
|---|---|---|
| T (마감 잔여 시간) | 0.35 | 지수 감쇠 — 마감 초과=1.0, 24h 후=0.12 |
| A (발신자 권한) | 0.25 | 조직 계층 거리 — CEO=1.0, 동료=0.5 |
| F (반복 추적) | 0.20 | 미응답 상태의 동일 발신자 메시지 수 (로그 스케일) |
| K (키워드 신호) | 0.10 | 정규식 매칭 — "urgent"=+0.9, "FYI"=−0.4 |
| S (소스·채널) | 0.10 | Slack DM=0.85, Jira blocker=0.90, 이메일 CC=0.35 |

```
urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S  →  레벨 1~5
```

**LLM 담당 영역 (의미 이해가 필요한 것만)**
- **액션 타입** — Reply / Approve / Review / FYI / No-action
- **1~2줄 요약** — 무엇을 해야 하는지 한 문장으로

**긴급도 5 항목 — 선택적 ReAct**

정량 점수가 최고 레벨인 항목에 한해, 교차 참조(이메일 내 Slack 링크, Jira 댓글 등)를 따라가며 추가 컨텍스트를 수집하는 ReAct 루프를 실행한다. 최대 5회 반복 후 종료.

### 3-3. 복귀 브리핑 리포트
```
[복귀 브리핑] 2026-05-13 오전 9:02
부재 기간: 5월 9일(금) 퇴근 ~ 5월 13일(화) 오전 9시
수집된 항목: 이메일 47건 / 슬랙 213건 / 지라 8건

▶ 지금 당장 처리 (오늘 마감 또는 이미 지남)
  1. [이메일] 김대표 → 계약서 최종 서명 요청 (마감: 5/13 오전)
  2. [지라] PROJ-402 배포 승인 대기 (마감: 5/12 → 초과)
  3. [슬랙] 박팀장 DM 3건 — 예산 승인 건

▶ 오늘 안에 처리
  4. [캘린더] 14:00 주간 회의 — 자료 준비 필요
  5. [이메일] 디자인팀 피드백 요청 14건 (묶음)

▶ 이번 주 내 처리
  ...

▶ 읽기만 하면 됨 (FYI)
  ...
```

### 3-4. 원클릭 액션
- 브리핑 카드에서 바로 답장 초안 생성
- 슬랙 메시지 즉시 회신
- 캘린더 일정 수락/거절
- 지라 이슈 상태 변경

### 3-5. 연락해야 할 사람 정리
- 내가 답장하지 않은 메시지를 기다리는 사람 목록
- 내가 블로커인 이슈의 담당자 목록
- 추천 답장 초안 제공

### 3-6. 작업 결산 (Daily/Weekly Summary)

하루 또는 한 주가 끝날 때, 오늘 처리한 항목과 남은 항목을 자동 집계해 "오늘 뭘 했는지"를 한눈에 정리해준다.

```
[작업 결산] 2026-05-13 오후 6:00

▶ 오늘 완료한 일  7건 / 예상 55분 → 실제 48분
  ✓ [이메일] 김대표 계약서 서명 완료
  ✓ [지라] PROJ-402 배포 승인
  ✓ [슬랙] 박팀장 예산 승인 3건 처리
  ... 외 4건

▶ 내일로 이월  3건
  · [이메일] 디자인팀 피드백 (스누즈: 내일 오전 10시)
  · [지라] PROJ-411 코드 리뷰 (마감: 5/15)
  · [캘린더] 주간 보고 자료 준비

▶ 오늘 통계
  소스별: 이메일 3건 · 슬랙 2건 · Jira 2건
  유형별: 승인 3건 · 답장 2건 · 검토 2건
  평균 응답 시간: 1시간 23분
```

### 3-7. KPI 보고서

개인 생산성 지표와 팀 관리자용 리포트를 주기적으로 생성한다.

**개인 KPI 대시보드**

| 지표 | 설명 |
|---|---|
| 완료율 | 할당 항목 중 기한 내 완료 비율 |
| 평균 응답 시간 | 수신 → 처리 완료까지 걸린 시간 |
| 초과 마감 비율 | 기한 초과 후 처리된 항목 비율 |
| 채널별 부하 | 소스별 수신 항목 수 및 처리 시간 비중 |
| 이월 누적 추이 | 주별 미완료 항목 잔여량 변화 |

**팀 관리자 리포트 (Team 플랜 이상)**
- 팀원별 완료율·응답 속도 비교
- 블로커 병목 지점 (누가 가장 오래 기다리고 있는가)
- 소스별 팀 전체 알림 부하량

**리포트 주기 및 형식**

```
일간 결산:  퇴근 시간(기본 오후 6시) 자동 생성 → 위젯 + 슬랙 DM
주간 리포트: 금요일 오후 5시 자동 생성 → 이메일 + PDF 다운로드
월간 리포트: 매월 마지막 영업일 → 팀 채널 공유 (Team 플랜)
```

### 3-8. 사내 규정 엔진 (Policy Engine)

회사마다 다른 업무 규정(보고 체계, 계약 한도, 대응 프로토콜 등)을 에이전트 동작에 반영한다.  
규정은 **3개 레이어**로 분리 적용된다.

#### 레이어 1 — 하드 오버라이드 (AI 판단 전, 데이터로 덮어씀)

AI가 판단하기 전에 정량 엔진의 점수를 강제로 변경하거나 액션을 고정한다.

```json
// policy.json 예시
{
  "hard_overrides": [
    {
      "name": "계약서_CEO_승인",
      "condition": { "keywords": ["계약서", "서명", "날인"], "sender_role": "external" },
      "action": { "urgency_level": 5, "action_type": "approve", "require_persons": ["CEO"] }
    },
    {
      "name": "VIP_고객_즉시처리",
      "condition": { "senders": ["cto@bigclient.com", "ceo@partner.com"] },
      "action": { "urgency_level": 5 }
    },
    {
      "name": "보안_이슈_강제리뷰",
      "condition": { "jira_labels": ["security", "compliance"] },
      "action": { "urgency_level": 5, "action_type": "review", "notify": ["security-team"] }
    }
  ]
}
```

#### 레이어 2 — 컨텍스트 주입 (AI 판단 시 시스템 프롬프트에 삽입)

AI가 **요약이나 초안**을 생성할 때 회사 맥락을 알아야 하는 경우.

```python
def build_system_prompt(user_policy: PolicyConfig) -> str:
    return f"""
당신은 {user_policy.company_name} 소속 {user_policy.user_role}의 업무 어시스턴트입니다.

[사내 커뮤니케이션 규정]
{user_policy.communication_rules}  
# 예: "외부 파트너에게는 반드시 경어체 사용"
# 예: "법무팀 관련 사안은 요약 없이 원문 그대로 전달"

[보고 체계]
{user_policy.reporting_structure}
# 예: "계약 관련 사안은 항상 법무팀장(kim@company.com)을 참조"

[프로젝트 우선순위]
{user_policy.project_priorities}
# 예: "Project-Alpha는 이번 분기 최우선 프로젝트"
"""
```

#### 레이어 3 — 가드레일 (AI 판단 후, 특정 액션 무조건 차단)

어떤 AI 판단이 나오더라도 허용하지 않는 액션.

```python
GUARDRAILS = [
    {
        "name": "자동_발송_금지",
        "rule": "action_type in ['reply', 'approve'] AND auto_send == True",
        "block": True,
        "reason": "모든 발송은 사용자 확인 후 진행"
    },
    {
        "name": "계약_자동승인_금지",
        "rule": "action_type == 'approve' AND source == 'email' AND '계약' in summary",
        "block": True,
        "reason": "계약 관련 승인은 사람이 직접 처리"
    },
    {
        "name": "외부공유_금지",
        "rule": "recipient_domain != company_domain AND content_label == 'confidential'",
        "block": True,
        "reason": "사내 기밀 문서 외부 공유 차단"
    }
]
```

#### Policy Engine 처리 순서

```
[수집된 item]
      │
      ▼
[레이어 1] Hard Override 검사
  → 조건 매칭 시 urgency/action_type 강제 설정
  → 매칭 없으면 패스
      │
      ▼
[Urgency Engine + Classifier]  ← 레이어 2 컨텍스트 프롬프트 주입됨
      │
      ▼
[레이어 3] Guardrail 검사
  → 차단 조건 매칭 시 해당 액션 버튼 비활성화 + 사유 표시
  → 감사 로그(audit log) 기록
      │
      ▼
[UI 카드 스트리밍]
```

#### Policy 설정 UI (Team/Enterprise 플랜)

```
┌─────────────────────────────────────────┐
│  사내 규정 설정                          │
│                                         │
│  ▶ 발신자 규정                          │
│    + VIP 발신자 추가         [추가]      │
│    + 도메인별 우선순위 설정  [추가]      │
│                                         │
│  ▶ 키워드 규정                          │
│    + 특정 키워드 → 긴급도 설정 [추가]   │
│                                         │
│  ▶ 가드레일                             │
│    ☑ 모든 발송 전 사용자 확인 (권장)    │
│    ☑ 계약서 자동 승인 차단              │
│    ☐ 야간 알림 차단 (오후 10시~오전 7시)│
└─────────────────────────────────────────┘
```

---

## 4. 사용자 시나리오

### 시나리오 A — 월요일 아침 출근
1. 오전 8:55 사무실 도착, WhatToDo 앱 열기
2. 에이전트가 주말 동안 수신된 항목 자동 분석 (30초)
3. 복귀 브리핑 화면 표시
4. 사용자가 TOP 3 항목을 처리하며 순서대로 체크
5. 나머지는 캘린더에 시간 블록으로 자동 배치

### 시나리오 B — 5일 휴가 복귀
1. 복귀 전날 밤, 앱이 푸시 알림: "내일 복귀 브리핑 준비 중입니다"
2. 출근 전 모바일로 브리핑 미리 확인
3. 사무실 도착 전 긴급 항목 2건 처리 완료
4. 팀원에게 "오늘 오전은 따라잡기 중" 자동 슬랙 공지 (선택)

### 시나리오 C — 미팅이 몰린 날 오후

> 복귀 상황이 아니어도, 연속 회의로 알림이 쌓였을 때 위젯이 따라잡기를 도와주는 경우.

1. 오후 2시, 오전 내내 미팅만 4개 연속으로 끝냄
2. 슬랙·이메일 알림이 47건 쌓여 있음 — 어디서부터 봐야 할지 막막
3. WhatToDo 위젯 열기 → 에이전트가 "미팅 중 수신 항목" 자동 집계
4. **긴급도 순 카드 3장**이 상단에 표시됨
   - 박팀장 DM: "오늘 오후 4시 전 승인 필요"
   - 고객사 이메일: 내일 오전 제안서 마감
   - Jira PR 리뷰 요청 (배포 블로킹 중)
5. 나머지 44건은 "FYI" 섹션으로 접혀 있음 → 무시해도 됨을 즉시 인지
6. 3건을 30분 안에 처리하고 체크 완료

### 시나리오 D — 퇴근 전 하루 결산 (Phase 2)

> 오늘 무엇을 했는지, 내일 무엇을 이어받는지 확인하는 루틴.

1. 오후 5시 55분, 위젯에 "오늘 결산 준비됐습니다" 알림
2. 결산 패널 열기
   - 완료 8건 / 예상 70분 → 실제 55분 ✓
   - 이월 2건 (내일 마감 1건, 이번 주 내 1건)
   - "오늘 슬랙 응답이 평균보다 빠릅니다 👍"
3. 이월 항목 2건을 내일 오전 캘린더 블록으로 자동 배치
4. 퇴근

### 시나리오 E — 주간 KPI로 업무 패턴 발견 (Phase 3)

> 반복되는 병목을 데이터로 인지하고 행동을 바꾸는 경우.

1. 금요일 오후 5시, 주간 KPI 리포트 슬랙 DM 수신
2. 리포트 확인
   - 완료율 68% — 지난 4주 평균(81%) 대비 낮음
   - Jira 초과 마감 비율 24% — 이번 주만 유독 높음
   - "월·화에 Jira 이슈가 집중 할당되는 패턴이 감지됩니다"
3. AI 제안: "월요일 오전 30분을 Jira 전용 시간 블록으로 예약하시겠어요?"
4. 수락 → 다음 주 월·화 오전 9시에 캘린더 블록 자동 생성

---

## 5. 기술 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                      Client Layer                       │
│       Streamlit App  /  Slack Bot  /  Mobile            │
│       ← REST 폴링으로 카드 목록 수신                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS / REST
┌────────────────────────▼────────────────────────────────┐
│                    API Gateway (FastAPI)                 │
│              Auth (OAuth2) · Rate Limit · Routing       │
└───────┬──────────────┬──────────────────────────────────┘
        │              │
┌───────▼──────┐ ┌─────▼──────────────────────────────────┐
│ Connector    │ │           Orchestrator Agent             │
│ Workers      │ │         (Python, LLM 미사용)             │
│ (병렬 실행)  │ │                                          │
│              │ │  ┌──────────────────────────────────┐   │
│ - Gmail ─────┼─┼─►│  Priority Queue (heapq)          │   │
│ - Slack ─────┼─┼─►│  수집 즉시 투입, 긴급도 추정으로 │   │
│ - Calendar ──┼─┼─►│  선처리 순서 결정               │   │
│ - Jira ──────┼─┼─►└──────────────┬───────────────────┘   │
│ - Notion     │ │                 │                        │
└──────────────┘ │  ┌──────────────▼───────────────────┐   │
                 │  │  Urgency Engine (정량 계산)        │   │
                 │  │  + Classifier (LLM: 액션·요약)    │   │
                 │  │  → 분류 완료 즉시 TinyDB 저장      │   │
                 │  └──────────────┬───────────────────┘   │
                 │                 │ (urgency=5 항목만)     │
                 │  ┌──────────────▼───────────────────┐   │
                 │  │  ReAct Loop (교차 참조 추가 수집) │   │
                 │  │  max 5 iterations                 │   │
                 │  └──────────────┬───────────────────┘   │
                 │                 │ (전체 완료 후)         │
                 │  ┌──────────────▼───────────────────┐   │
                 │  │  Summarizer (브리핑 헤더 생성)    │   │
                 │  └──────────────────────────────────┘   │
                 └─────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────┐
│                      Data Layer                          │
│   TinyDB (JSON 파일 기반)  ·  heapq (인메모리 우선순위 큐)│
│   → Phase 2+: PostgreSQL + Redis 교체 가능               │
└─────────────────────────────────────────────────────────┘
```

### 에이전트 + 툴 구성

"다음에 뭘 할지 결정하지 않으면 Tool이다."

| 구분 | 컴포넌트 | 역할 | 구현 |
|---|---|---|---|
| **Tool** | fetch | 소스별 메시지 수집 | OAuth API 커넥터 래핑, LLM 미사용 |
| **Tool** | scoring | 정량 5-신호 긴급도 계산 | 순수 Python, LLM 미사용 |
| **Tool** | classify | 액션 타입 분류 + 1~2줄 요약 | LLM Fast 1-shot |
| **Tool** | storage | TinyDB CRUD | 순수 Python |
| **Agent** | Briefing Agent | tool_use 루프로 브리핑 파이프라인 조율 | LLM Smart + TOOL_REGISTRY |
| **Agent** | Action Agent | 답장 초안 생성 (on-demand) | LLM Smart |

---

## 6. 데이터 모델

```python
# 수집된 항목 단위
class WorkItem:
    id: str
    source: Literal["gmail", "slack", "calendar", "jira", "notion"]
    raw_content: str
    summary: str              # AI 요약 (1~2문장)
    urgency: int              # 1~5 (5 = 최고 긴급)
    urgency_breakdown: dict   # {"T": 0.78, "A": 0.80, ...}
    action_type: Literal["reply", "approve", "review", "fyi", "none"]
    due_at: datetime | None
    from_person: Person | None
    linked_items: list[str]   # 연관 항목 ID
    status: Literal["pending", "done", "snoozed"]
    created_at: datetime
    completed_at: datetime | None   # 결산 집계용
    actual_minutes: int | None      # 실제 처리 시간 (완료 시 기록)
    briefing_id: str

# 복귀 브리핑 단위
class Briefing:
    id: str
    user_id: str
    absence_start: datetime
    absence_end: datetime
    generated_at: datetime
    items: list[WorkItem]
    summary_text: str

# 일간 작업 결산
class DailySummary:
    id: str
    user_id: str
    date: date
    completed_items: list[WorkItem]
    carried_over_items: list[WorkItem]
    stats: DailyStats

class DailyStats:
    total_assigned: int
    total_completed: int
    completion_rate: float          # completed / assigned
    avg_response_minutes: float     # 수신 → 완료 평균 시간
    overdue_count: int
    by_source: dict[str, int]       # {"gmail": 3, "slack": 2, ...}
    by_action_type: dict[str, int]  # {"reply": 2, "approve": 3, ...}
    estimated_minutes: int
    actual_minutes: int

# KPI 리포트 (주간/월간)
class KPIReport:
    id: str
    user_id: str
    period: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    generated_at: datetime
    daily_summaries: list[DailySummary]
    aggregated: KPIAggregated
    narrative: str              # LLM Smart 티어가 생성한 자연어 요약

class KPIAggregated:
    avg_completion_rate: float
    avg_response_minutes: float
    overdue_ratio: float
    busiest_source: str
    carryover_trend: list[int]  # 날짜별 이월 항목 수 추이
    total_items_processed: int
    total_time_saved_estimate: int  # WhatToDo 없이 걸렸을 추정 시간 vs 실제
```

---

## 7. 개인정보 및 보안

- 이메일·메시지 원문은 처리 후 즉시 삭제, 요약본만 저장
- OAuth 토큰은 암호화 저장 (AES-256)
- 모든 AI 처리는 Anthropic API (데이터 학습에 사용되지 않음, Anthropic 정책 기준)
- SOC 2 Type II 준수 목표 (v2)
- 온프레미스 배포 옵션 제공 예정 (기업 고객)

---

## 8. 수익 모델

| 플랜 | 대상 | 가격 | 포함 내용 |
|---|---|---|---|
| Free | 개인 | 무료 | 소스 2개, 월 브리핑 10회 |
| Pro | 개인 | $9/월 | 소스 무제한, 브리핑 무제한, 액션 기능 |
| Team | 팀 | $6/인/월 | Pro + 팀 워크스페이스, 관리자 대시보드 |
| Enterprise | 기업 | 협의 | 온프레미스, SSO, 감사 로그 |

---

## 9. 개발 로드맵

### Phase 1 — MVP (4주, ~2026-06-13 목표)

#### MVP 확정 범위

| 포함 | 제외 (Phase 2+) |
|---|---|
| Gmail + Slack + Google Calendar 커넥터 | Jira / Linear / Notion 커넥터 |
| Urgency Engine (정량 5-신호) | ReAct Agent |
| Classifier (LLM Fast 티어: 액션 타입 + 요약) | 원클릭 답장 초안 |
| Priority Queue (heapq) + REST API | 일간 결산 / KPI 리포트 |
| Summarizer (브리핑 헤더) | Policy Engine |
| Streamlit 체크리스트 UI | 슬랙 봇 인터페이스 |
| OAuth 인증 (Gmail, Slack) | 스누즈 기능 |

#### 주차별 일정

```
Week 1 (Setup & Auth)       Week 2 (Core Pipeline)
─────────────────────       ──────────────────────
□ 프로젝트 초기 세팅         □ Slack 커넥터
  FastAPI + TinyDB            □ Google Calendar 커넥터
  Streamlit 뼈대              □ Urgency Engine 구현
□ Gmail OAuth 연동            □ Priority Queue (heapq)
  (가장 복잡 → 먼저 해결)     □ REST API 기초
□ 데이터 모델 확정
□ API 인터페이스 정의

Week 3 (AI + UI)            Week 4 (통합 & 마무리)
─────────────────────       ──────────────────────
□ Classifier (Fast) 연동    □ End-to-end 통합 테스트
□ Summarizer (Smart) 연동   □ 에러 처리 / 폴백
□ Streamlit UI 완성         □ 환경 변수 / 배포 설정
  체크리스트 인터랙션          □ 버그 수정
  섹션별 카드 표시             □ 데모 준비
□ REST API 연결
```

#### 팀 역할 분리 — 6인 1인 1에이전트

| # | 담당 | 핵심 구현 범위 |
|---|---|---|
| 1 | **Briefing Agent** | `agents/briefing_agent.py` (TOOL_REGISTRY + tool_use 루프), `models.py`, `scheduler.py` |
| 2 | **Gmail Fetch Tool** | `tools/fetch.py` (gmail 부분), `connectors/gmail.py`, `routers/auth.py` (OAuth) |
| 3 | **Slack + Calendar Fetch Tool** | `tools/fetch.py` (slack/calendar), `connectors/slack.py`, `connectors/calendar.py` |
| 4 | **Scoring Tool** | `tools/scoring.py` — 5-신호 가중합 공식, 단위 테스트 |
| 5 | **Classify + Storage Tool** | `tools/classify.py` (LLM Fast 1-shot), `tools/storage.py` (TinyDB CRUD) |
| 6 | **Streamlit UI** | `app.py`, `pages/` 전체, `mock_data.py` |

```
의존성 흐름 (→ 는 "출력 스키마를 받아야 작업 가능")

Fetch Tool #2 ─┐
Fetch Tool #3 ─┼─► Briefing Agent #1 ─► Scoring Tool #4 ─► Classify Tool #5 ─► Streamlit #6
               │       (tool_use 루프)                                                ▲
               └──────────────────────────────────────────────────────────────────────┘
                          (WorkCard·BriefingResult Pydantic 모델 Week 1 확정 → #6 mock 개발 시작)
```

```
Week 1                  Week 2                  Week 3                  Week 4
────────────────────    ────────────────────    ────────────────────    ────────────────────
#1 FastAPI 뼈대         #1 Priority Queue       #1 파이프라인 연결       전원 통합·버그수정
   TinyDB 설계             REST API 서버            에러 폴백
   스키마 확정 (전원)
                        #2 Gmail API 수집        #2 스레드 묶음          데모 시나리오 검증
#2 Gmail OAuth 완료        파싱 로직               중복 제거 마무리

#3 Slack OAuth 완료     #3 Slack 메시지 수집     #3 Calendar 수집
                           DM·멘션 파싱             미수락 초대 처리

#4 T·A·F 신호 구현      #4 K·S 신호 구현         #4 fast_urgency 완료
   단위 테스트 작성         전체 공식 검증             단위 테스트 완료

#5 LLMClient 래퍼 설정  #5 Classifier 프롬프트   #5 Summarizer 연동
   Fast 티어 연결 확인       액션 타입 분류           브리핑 헤더 생성

#6 Streamlit 앱 세팅    #6 mock 데이터로         #6 REST API 연결
   페이지 구조              카드 UI 구현             실시간 카드 렌더링
                            섹션·체크리스트          체크 완료 인터랙션
```

> **Week 1 필수 합의 (담당 #1 주도, 전원 참여)**  
> `WorkCard` · `BriefingHeader` Pydantic 모델 확정 → #6이 mock 데이터로 독립 개발 시작 가능

#### 브랜치 전략

```
main          ← 배포 가능 상태만 병합
  └ dev       ← 주간 통합 브랜치
      ├ feat/briefing-agent
      ├ feat/gmail-tool
      ├ feat/slack-calendar-tool
      ├ feat/scoring-tool
      ├ feat/classify-tool
      └ feat/streamlit-ui
```

- PR은 `dev`로만. `main` 병합은 주 1회 (금요일 데모 후).
- 커밋 컨벤션: `feat:` / `fix:` / `chore:` / `docs:`

---

### Phase 2 — 액션 + 결산 (5주)
- [ ] 원클릭 답장 초안 (Action Agent)
- [ ] 슬랙 봇 인터페이스
- [ ] Jira / Linear 연동
- [ ] 스누즈 기능
- [ ] 일간 작업 결산 (완료 항목 집계 + 이월 목록)
- [ ] 완료 시 실제 처리 시간 기록

### Phase 3 — 개인화 + KPI (5주)
- [ ] 주간 KPI 리포트 자동 생성
- [ ] 개인 KPI 대시보드 UI
- [ ] Policy Engine (사내 규정)
- [ ] 사용 패턴 학습 (중요도 재조정)
- [ ] 복귀 전날 사전 알림
- [ ] 모바일 앱 (PWA)
- [ ] Notion / Confluence 연동

### Phase 4 — 팀 기능 (6주)
- [ ] 팀 대시보드
- [ ] 블로커 감지 & 알림
- [ ] 팀 관리자용 KPI 리포트 (팀원별 완료율·응답 속도)
- [ ] 월간 리포트 PDF 내보내기
- [ ] 온프레미스 배포

### 확장 아이디어 (시간 여유 시 검토)

> 로드맵에 포함되지 않은 선택적 기능. 우선순위 없음.

- [ ] **사내 문서 RAG** — 온보딩 시 사용자가 사내 문서(조직도, 규정집, 프로젝트 개요 등) 업로드 → 개인 벡터 스토어 구축 → Authority 신호 자동 산출 + Policy Engine L2 자동화 + ReAct `search_company_docs()` 도구 추가. 사용자별 격리 컬렉션(ChromaDB).
- [ ] **브라우저 확장 위젯** — Streamlit 전체 페이지 대신 브라우저 툴바 팝업 형태. FastAPI REST 엔드포인트 추가만으로 전환 가능, 백엔드 재사용.
- [ ] **발신자 히스토리 RAG** — 과거 수신 항목 임베딩 → 동일 발신자 컨텍스트 자동 요약 + 초안 스타일 학습.

---

## 10. 성공 지표 (KPI)

### 서비스 운영 KPI

| 지표 | MVP 목표 | 6개월 목표 |
|---|---|---|
| 복귀 후 첫 브리핑 조회율 | 70% | 85% |
| 브리핑 생성 시간 | < 60초 | < 30초 |
| 분류 정확도 (사용자 피드백) | 75% | 90% |
| 월간 활성 사용자 | 500 | 5,000 |
| 유료 전환율 | 10% | 20% |
| 일간 결산 열람율 (DAU 대비) | 50% | 70% |
| 주간 KPI 리포트 열람율 | — | 60% |

### 사용자에게 제공되는 KPI 지표 (서비스 내 대시보드)

```
[개인 주간 KPI] 2026-05-13 (5월 2주차)

완료율          ████████░░  82%   (지난주 74% → +8%)
평균 응답 시간  2시간 14분        (지난주 3시간 01분 → 개선)
초과 마감 비율  ░░░░░░░░░░   8%   (지난주 15% → 개선)
이월 추이       ↓ 11→9→7→5→3건  (감소 중)

채널별 부하
  Gmail  ████████  45%
  Slack  █████     28%
  Jira   ████      22%
  기타   ░          5%

절약 추정 시간: 약 3.2시간 (WhatToDo 미사용 시 대비)
```

---

## 11. 경쟁 분석

| 서비스 | 강점 | 약점 | WhatToDo 차별점 |
|---|---|---|---|
| Superhuman | 이메일 UX | 이메일만 | 멀티소스 통합 |
| Notion AI | 문서 요약 | 능동적 수집 없음 | 자동 수집·분류 |
| Motion | 일정 최적화 | AI 분류 부족 | 복귀 특화 브리핑 |
| Slack AI | 채널 요약 | Slack 전용 | 채널 횡단 통합 |
