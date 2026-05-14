# WhatToDo — 직장인 업무 복귀 어시스턴트 기획서

## 1. 서비스 개요

**WhatToDo**는 출근 직후 또는 휴가·병가·출장 복귀 직후, 쌓인 업무와 알림을 AI 에이전트가 자동으로 수집·분류·요약해 "오늘 무엇부터 해야 하는가"를 한눈에 제시하는 서비스다.

| 항목 | 내용 |
|---|---|
| 서비스명 | WhatToDo |
| 타깃 사용자 | 이메일·슬랙·지라 등 여러 도구를 사용하는 직장인 |
| 핵심 가치 | 복귀 후 첫 30분을 허비하지 않는다 |
| 서비스 형태 | 웹 앱 + 슬랙 봇 (MVP), 모바일 앱 (v2) |

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

---

## 5. 기술 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                      Client Layer                       │
│       Web App (React)  /  Slack Bot  /  Mobile          │
│       ← WebSocket 스트리밍으로 카드 실시간 수신          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                    API Gateway (FastAPI)                 │
│              Auth (OAuth2) · Rate Limit · Routing       │
└───────┬──────────────┬──────────────────────────────────┘
        │              │
┌───────▼──────┐ ┌─────▼──────────────────────────────────┐
│ Connector    │ │           Orchestrator Agent             │
│ Workers      │ │         (Claude claude-sonnet-4-6)       │
│ (병렬 실행)  │ │                                          │
│              │ │  ┌──────────────────────────────────┐   │
│ - Gmail ─────┼─┼─►│  Priority Queue (Redis)          │   │
│ - Slack ─────┼─┼─►│  수집 즉시 투입, 긴급도 추정으로 │   │
│ - Calendar ──┼─┼─►│  선처리 순서 결정               │   │
│ - Jira ──────┼─┼─►└──────────────┬───────────────────┘   │
│ - Notion     │ │                 │                        │
└──────────────┘ │  ┌──────────────▼───────────────────┐   │
                 │  │  Urgency Engine (정량 계산)        │   │
                 │  │  + Classifier (LLM: 액션·요약)    │   │
                 │  │  → 분류 즉시 UI 스트리밍           │   │
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
│   PostgreSQL (항목 저장)  ·  Redis (우선순위 큐/캐시)    │
│   Vector DB - pgvector (의미 검색)                       │
└─────────────────────────────────────────────────────────┘
```

### 에이전트 구성

| 컴포넌트 | 역할 | 구현 |
|---|---|---|
| Orchestrator | 전체 흐름 제어, 스트리밍 조율 | Claude claude-sonnet-4-6 |
| Connector Workers | 각 소스 병렬 수집 → Priority Queue 투입 | OAuth API 커넥터 |
| Urgency Engine | 정량 5-신호 계산 (T·A·F·K·S) | 순수 Python (LLM 미사용) |
| Classifier | 액션 타입 분류 + 1~2줄 요약 | Claude claude-haiku-4-5 (비용 최적화) |
| ReAct Agent | 긴급도 5 항목 교차 참조 추가 수집 | Claude claude-sonnet-4-6 + Tool Registry |
| Summarizer | 전체 브리핑 헤더·통계 생성 | Claude claude-sonnet-4-6 |
| Action Agent | 답장 초안 생성, 외부 API 호출 | Claude claude-sonnet-4-6 + 도구 |

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
    narrative: str              # Claude Sonnet이 생성한 자연어 요약

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

### Phase 1 — MVP (8주)
- [ ] Gmail + Google Calendar 연동
- [ ] Slack 연동
- [ ] 기본 분류 및 브리핑 생성
- [ ] 웹 앱 UI (브리핑 조회)

### Phase 2 — 액션 + 결산 (5주)
- [ ] 원클릭 답장 초안
- [ ] 슬랙 봇 인터페이스
- [ ] Jira / Linear 연동
- [ ] 스누즈 & 할 일 목록 연동
- [ ] 일간 작업 결산 (완료 항목 집계 + 이월 목록)
- [ ] 완료 시 실제 처리 시간 기록

### Phase 3 — 개인화 + KPI (5주)
- [ ] 주간 KPI 리포트 자동 생성
- [ ] 개인 KPI 대시보드 UI
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
