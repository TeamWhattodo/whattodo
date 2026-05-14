# WhatToDo — 에이전트 워크플로우

## 전체 흐름 개요

```
                      ┌─────────────────────────────────┐
                      │         트리거 종류               │
                      │  A) 복귀 브리핑  (출근/복귀 시)  │
                      │  B) 일간 결산   (매일 오후 6시)  │
                      │  C) 주간 KPI    (금요일 오후 5시) │
                      └────────────┬────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     [복귀 브리핑 플로우]   [일간 결산 플로우]   [주간 KPI 플로우]
              │                    │                    │
[1] 트리거 감지         [1] 오늘 WorkItem 조회  [1] 주간 DailySummary 조회
              │                    │                    │
[2] Connector Workers   [2] DailyStats 집계    [2] KPIAggregated 집계
    병렬 수집            (순수 연산)            (순수 연산 + 전주 비교)
              │                    │                    │
[3] Priority Queue      [3] Narrative 생성     [3] Narrative 생성
              │             (Haiku)                (Sonnet)
              │                    │                    │
[4] Urgency Engine      [4] DailySummary 저장  [4] KPIReport 저장
    (정량 계산)                     │                    │
              │          [5] 결산 위젯 업데이트 [5] 리포트 전송
    ├─urgency 1~4                                  (이메일/슬랙/PDF)
    │   └► Classifier ──► UI 스트리밍
    └─urgency 5
        └► ReAct Loop ──► Classifier ──► UI 스트리밍
              │
[5] Summarizer — 브리핑 헤더 생성
              │
[6] 브리핑 확정 제시
              │
[7] Action Agent (on-demand)
```

---

## 상세 워크플로우

### Step 1. 트리거 감지

```
트리거 종류:
  A) 수동 — 사용자가 앱 열기 / "브리핑 시작" 클릭
  B) 자동 — 마지막 로그인으로부터 N시간 경과 (기본값: 8시간)
  C) 스케줄 — 매일 오전 8:30 자동 실행 (사용자 설정)
  D) 복귀 설정 — 사용자가 "휴가 종료일" 캘린더에 등록

입력:
  - user_id
  - absence_start (마지막 활동 시각 또는 명시적 부재 시작)
  - absence_end   (현재 시각 또는 명시적 복귀 시각)

출력:
  - briefing_session_id
  - collection_window: { start, end }
```

---

### Step 2. Connector Workers — 병렬 수집 + Priority Queue 투입

> 각 소스 커넥터는 병렬로 실행된다. 수집이 끝날 때까지 기다리지 않고 항목 단위로 즉시 큐에 투입한다.

```
┌──────────┐  item₁ ──►┐
│  Gmail   │  item₂ ──►│
│Connector │  item₃ ──►│   ┌─────────────────────────────┐
└──────────┘           ├──►│      Priority Queue          │
┌──────────┐  item₄ ──►│   │  (Redis Sorted Set)          │
│  Slack   │  item₅ ──►│   │                              │
│Connector │           ├──►│  score = fast_urgency(item)  │
└──────────┘           │   │  (키워드+발신자만 보는 0.1초  │
┌──────────┐  item₆ ──►│   │   초경량 추정)               │
│Calendar  │           ├──►│                              │
│Connector │           │   │  [CEO 이메일, est≈0.9]  ←처리│
└──────────┘           │   │  [Jira blocker, est≈0.85]    │
┌──────────┐  item₇ ──►│   │  [DM×3, est≈0.7]            │
│  Jira    │           ├──►│  [채널 멘션, est≈0.4]        │
│Connector │           │   │  ...                         │
└──────────┘           │   └─────────────┬────────────────┘
                       │                 │ 큐에서 꺼내 처리
                       │                 ▼
                       │       Urgency Engine + Classifier
                       │                 │
                       │                 ▼ 분류 완료 즉시
                       │           WebSocket → UI 카드 스트리밍
```

**Gmail Connector**
```
1. OAuth2 토큰으로 Gmail API 호출
2. 쿼리: is:unread after:{absence_start}
3. 각 이메일에서 추출:
   - sender, subject, snippet, received_at, thread_id
   - 첨부파일 여부, 캘린더 초대 여부
4. 스레드 단위로 묶어 중복 제거
5. 최대 200건 (초과 시 최신순)
```

**Slack Connector**
```
1. Slack Bot Token으로 API 호출
2. 수집 대상:
   - conversations.history — 멘션(@me) 포함 메시지
   - im.history          — DM
   - 미완료 reminder 목록
3. 각 메시지에서 추출:
   - channel, sender, text, ts, thread_ts
   - 반응(emoji) 여부 (내가 이미 확인했는지 시그널)
4. 스레드 단위 묶음 처리
```

**Calendar Connector**
```
1. Google Calendar API 호출
2. 수집 대상:
   - 부재 기간 중 수락하지 않은 초대
   - 오늘 ~ 3일 이내 일정 (준비 필요 여부 판단용)
   - 마감일이 지난 이벤트
3. 각 이벤트에서 추출:
   - title, start, end, attendees, description
   - organizer, RSVP status
```

**Jira/Linear Connector**
```
1. API 토큰으로 호출
2. JQL 쿼리: assignee = currentUser() AND (
     updated >= {absence_start} OR
     due <= {absence_end+3days}
   )
3. 각 이슈에서 추출:
   - key, summary, status, priority, due_date
   - assignee, reporter, comments (부재 중 추가분)
   - 블로커 여부 (is_blocked_by, blocks)
```

---

### Step 3. Urgency Engine — 정량 긴급도 계산

> 순수 Python. LLM 호출 없음. 항목당 ~1ms.

**5-신호 가중합 공식**

```python
urgency_score = 0.35·T + 0.25·A + 0.20·F + 0.10·K + 0.10·S
urgency_level = ceil(urgency_score * 5)   # → 1~5
```

**신호별 계산 방법**

```python
# T — 시간 잔여율 (마감 기준 지수 감쇠)
def time_score(due_at, received_at, now) -> float:
    if due_at:
        hours_left = (due_at - now).total_seconds() / 3600
        if hours_left <= 0: return 1.0          # 이미 초과
        return 1 - exp(-3 / max(hours_left, 0.5))
    else:
        hours_elapsed = (now - received_at).total_seconds() / 3600
        return min(hours_elapsed / 72, 0.6)     # 마감 없음, 최대 0.6

# A — 발신자 권한 (조직 계층 거리)
AUTHORITY = { "ceo": 1.0, "c_level": 0.9, "direct_manager": 0.8,
              "peer": 0.5, "external_client": 0.75, "unknown": 0.3 }

# F — 반복 추적 (미응답 동일 발신자 메시지 수, 로그 스케일)
followup = min(log1p(unanswered_count) / log1p(5), 1.0)

# K — 키워드 신호 (정규식, clamp to [0, 1])
KEYWORDS = { r"urgent|긴급": +0.9, r"ASAP|오늘까지": +0.8,
             r"마감|deadline": +0.6, r"FYI|참고": -0.4 }

# S — 소스·채널 유형
SOURCE = { ("slack","dm"): 0.85, ("jira","blocker"): 0.90,
           ("email","direct"): 0.70, ("email","cc"): 0.35 }
```

**출력 예시**

```json
{
  "urgency_score": 0.821,
  "urgency_level": 5,
  "breakdown": {
    "T": 0.78,
    "A": 0.80,
    "F": 0.60,
    "K": 0.80,
    "S": 0.70
  }
}
```

---

### Step 3-a. ReAct Loop — 긴급도 5 항목 전용

> urgency_level=5 항목에만 실행. Claude Sonnet + Tool Registry.

```
Reason: "이메일 본문에 Slack 스레드 링크가 있다. 해당 스레드를 봐야
         맥락을 파악할 수 있다."
Act:    fetch_slack_thread(channel="proj-alpha", ts="1234567890.123")
Observe: [스레드 내용 수신]

Reason: "스레드에서 박팀장이 최종 결정을 요청했다. 추가 수집 불필요."
→ STOP (2 iterations)
```

**Tool Registry (ReAct에서만 사용)**

```python
tools = [
    fetch_email_thread(thread_id),        # 이메일 스레드 전체
    fetch_slack_thread(channel, ts),       # Slack 스레드 원문
    fetch_jira_comments(issue_key),        # Jira 댓글 전체
    search_calendar(keyword, date_range),  # 캘린더 검색
    get_sender_info(email),                # 발신자 직책·관계
    extract_references(text),              # 본문 내 링크·이슈키 추출
]
```

**종료 조건 (먼저 충족되는 것)**

```python
STOP_CONDITIONS = [
    lambda s: s.iteration >= 5,
    lambda s: "ENOUGH_CONTEXT" in s.scratchpad,
    lambda s: len(s.new_references) == 0,   # 더 따라갈 참조 없음
]
```

---

### Step 3-b. Classifier — 액션 타입 + 요약

> Claude Haiku. 항목당 ~200 토큰. 긴급도는 이미 계산되었으므로 의미 이해만 담당.

```
입력: raw_item + urgency_result (+ ReAct 추가 컨텍스트 if any)
출력: action_type, summary

프롬프트:
  System: "아래 업무 항목의 액션 타입과 1~2줄 요약을 JSON으로 반환하라.
           긴급도는 이미 계산되었으니 판단하지 않는다."

  User:   "[Gmail] 김대표 → 계약서 서명 요청\n내용: ..."

  → {
      "action_type": "approve",
      "summary": "CEO가 계약서 최종 서명을 요청.",
      "estimated_time_min": 10,
      "requires_contact": ["김대표"]
    }
```

**액션 타입**

```
reply    — 나의 답변·응답이 필요한 경우
approve  — 내 승인·서명·수락이 필요한 경우
review   — 내가 검토해야 하는 문서·코드·디자인
fyi      — 읽기만 하면 되는 정보성 항목
none     — 이미 처리됐거나 불필요한 항목
```

---

### Step 4. Summarizer Agent — 브리핑 생성

> Claude Sonnet으로 품질 확보.

```
입력: classified_items[] (전체 분류 완료 항목)
출력: Briefing (구조화된 브리핑 객체)

처리 단계:
  1. 그룹핑
     - urgency 5 → "지금 당장"
     - urgency 3~4 + 오늘 마감 → "오늘 안에"
     - urgency 2~3 → "이번 주 내"
     - action_type == "fyi" → "읽기만 하면 됨"

  2. 같은 주제 묶음 처리
     - 동일 발신자의 연속 메시지 → 1건으로 묶어 요약
     - 동일 프로젝트 관련 이슈 → 그룹 레이블 부여

  3. "연락해야 할 사람" 목록 생성
     - 내가 답하지 않아 기다리는 사람
     - 내가 블로커인 이슈의 담당자
     - 내가 수락/거절하지 않은 초대 주최자

  4. 브리핑 헤더 문구 생성
     - 부재 기간 요약
     - 전체 항목 수 및 긴급 항목 수
     - 예상 처리 시간 합계
```

**브리핑 출력 구조**

```json
{
  "briefing_id": "brfg_20260513_001",
  "generated_at": "2026-05-13T09:02:00",
  "absence": {
    "start": "2026-05-09T18:00:00",
    "end": "2026-05-13T09:00:00",
    "duration_days": 4
  },
  "stats": {
    "total": 268,
    "urgent": 3,
    "today": 7,
    "fyi": 180,
    "estimated_minutes": 85
  },
  "sections": {
    "immediate": [...],
    "today": [...],
    "this_week": [...],
    "fyi": [...]
  },
  "contacts_needed": [
    {
      "person": "김대표",
      "reason": "계약서 서명 답변 대기 중",
      "channel": "email",
      "draft_available": true
    }
  ],
  "summary_text": "4일 부재 동안 268건이 수신됐습니다. 긴급 처리가 필요한 항목은 3건이며..."
}
```

---

### Step 5. 브리핑 제시

```
UI 렌더링 순서:
  1. 헤더 카드 — 부재 기간, 통계, 예상 처리 시간
  2. "지금 당장" 섹션 (강조 표시)
  3. "연락해야 할 사람" 패널
  4. "오늘 안에" 섹션
  5. "이번 주 내" 섹션 (접힌 상태)
  6. "FYI" 섹션 (접힌 상태)

각 카드 구성:
  ┌─────────────────────────────────────┐
  │ [출처 아이콘] 제목 요약 (1줄)       │
  │ 발신자 · 시간 · 예상 처리 시간      │
  │ ─────────────────────────────────── │
  │ [완료] [초안 작성] [스누즈] [열기]  │
  └─────────────────────────────────────┘
```

---

### Step 6. Action Agent — 사용자 액션 처리

> 사용자가 카드에서 액션을 선택할 때 실행.

```
액션 A: "초안 작성" 클릭
  입력: work_item + user_context
  처리:
    - Claude Sonnet이 답장/댓글 초안 생성
    - 사용자 어조(formal/casual) 반영
    - 사용자 확인 → 수정 → 전송
  출력: draft_text → 사용자 편집 인터페이스

액션 B: "완료" 체크
  처리:
    - status = "done" 업데이트
    - 해당 소스 읽음 처리 시도 (가능한 경우)
    - 연관된 "연락해야 할 사람" 목록에서 제거

액션 C: "스누즈"
  입력: snooze_until (사용자 선택)
  처리:
    - status = "snoozed"
    - snooze_until 시각에 알림 스케줄링

액션 D: "캘린더 블로킹"
  처리:
    - 완료 안 된 항목의 예상 시간 합산
    - Google Calendar에 "업무 정리" 블록 생성 제안
```

---

---

## 작업 결산 워크플로우

### 트리거

```
A) 스케줄 — 매일 오후 6시 (사용자 설정 가능)
B) 수동   — 위젯의 "오늘 결산" 버튼 클릭
C) 주간   — 금요일 오후 5시 (주간 KPI 리포트 포함)
```

### 결산 생성 흐름

```
[트리거]
    │
    ▼
[1] 오늘 날짜 기준 WorkItem 조회
    - status = "done" AND completed_at >= 오늘 00:00  → 완료 목록
    - status = "pending" OR "snoozed"                → 이월 목록
    │
    ▼
[2] DailyStats 집계 (순수 연산, LLM 미사용)
    - completion_rate = done / (done + pending)
    - avg_response_minutes = mean(completed_at - created_at)
    - overdue_count = count(due_at < completed_at)
    - by_source, by_action_type 카운트
    │
    ▼
[3] Narrative 생성 (Claude Haiku, ~300 토큰)
    - "오늘 7건을 처리했습니다. 평균 응답 시간이 어제보다 32분 단축됐습니다."
    - 이월 항목 중 내일 마감인 것 강조
    │
    ▼
[4] DailySummary 저장 → DB
    │
    ▼
[5] 결산 위젯 업데이트 + 슬랙 DM 발송 (선택)
```

### 결산 위젯 스케치

```
┌─────────────────────────────────────┐
│ 오늘 결산  2026-05-13  ✕           │
│ ──────────────────────────────────  │
│ ✅ 완료  7건  ·  실제 48분          │
│ ⏭  이월  3건  ·  예상 35분         │
│                                     │
│ 완료율  ████████░░  70%             │
│ 응답속도  1h 23m  (↓ 어제보다 빠름) │
│                                     │
│ 잘한 점: 긴급 항목 3건 모두 처리    │
│ 내일 주의: 디자인 피드백 마감 임박  │
│                                     │
│ [주간 KPI 보기]  [내일 브리핑 예약] │
└─────────────────────────────────────┘
```

---

## KPI 리포트 워크플로우

### 주간 리포트 생성 흐름

```
[금요일 오후 5시 스케줄]
    │
    ▼
[1] 이번 주 DailySummary 5건 조회 (월~금)
    │
    ▼
[2] KPIAggregated 집계 (순수 연산)
    - avg_completion_rate: 일간 완료율 평균
    - avg_response_minutes: 전체 응답 시간 평균
    - overdue_ratio: 초과 마감 항목 / 전체
    - busiest_source: 채널별 항목 수 중 최대값
    - carryover_trend: [월 11건, 화 9건, 수 7건, 목 5건, 금 3건]
    │
    ▼
[3] 지난 주 KPIAggregated와 비교 → 증감 계산
    │
    ▼
[4] Narrative 생성 (Claude Sonnet, ~500 토큰)
    입력: aggregated + prev_week_aggregated
    출력:
      "이번 주 완료율이 82%로 지난주(74%)보다 8%p 향상됐습니다.
       평균 응답 시간도 47분 단축됐습니다. 다만 Jira 이슈 초과 마감
       비율이 15%로 다소 높습니다. 다음 주에는 Jira 항목을 브리핑
       상단에서 먼저 처리하는 루틴을 추천합니다."
    │
    ▼
[5] KPIReport 저장 → DB
    │
    ▼
[6] 리포트 전송
    - 이메일 (사용자 선택)
    - 슬랙 DM
    - 앱 내 알림
    - PDF 내보내기 (Pro 이상)
```

### KPI 리포트 출력 구조

```json
{
  "report_id": "kpi_weekly_20260513",
  "period": "weekly",
  "period_start": "2026-05-09",
  "period_end": "2026-05-13",
  "aggregated": {
    "avg_completion_rate": 0.82,
    "avg_response_minutes": 83,
    "overdue_ratio": 0.08,
    "busiest_source": "gmail",
    "carryover_trend": [11, 9, 7, 5, 3],
    "total_items_processed": 47,
    "total_time_saved_estimate": 192
  },
  "vs_prev_week": {
    "completion_rate_delta": +0.08,
    "response_time_delta": -47,
    "overdue_ratio_delta": -0.07
  },
  "narrative": "이번 주 완료율이 82%로...",
  "recommendations": [
    "Jira 항목 초과 마감 비율 개선 필요",
    "월요일 브리핑 처리 시간이 평균보다 40% 길음 — 월요일 오전 집중 블록 추천"
  ]
}
```

---

## 에러 처리 및 폴백

```
소스 연결 실패:
  → 해당 소스 스킵 + 사용자에게 "Gmail 연결 오류" 배지 표시
  → 나머지 소스로 브리핑 생성 계속

AI 분류 실패 (항목):
  → urgency=3, action_type="review" 기본값으로 "오늘 안에" 섹션 배치
  → 사용자가 수동으로 재분류 가능

브리핑 생성 타임아웃 (>60초):
  → 수집된 항목 중 urgency 4~5만 먼저 제시 (부분 브리핑)
  → 백그라운드에서 나머지 처리 후 갱신

토큰 한도 초과 (항목 수 과다):
  → Classifier: 배치 처리 (50건씩)
  → Summarizer: 중요도 하위 항목은 카운트만 포함, 상세 내용 생략
```

---

## 데이터 흐름 다이어그램

```
[외부 소스]      [Priority Queue]    [처리 계층]           [클라이언트]
    │                  │                 │                      │
Gmail ──item─────►│               │                      │
Slack ──item─────►│  Redis        │                      │
Cal   ──item─────►│  Sorted Set   ├──► Urgency Engine    │
Jira  ──item─────►│  (score=      │    (Python, ~1ms)    │
                  │   fast_est)   │         │            │
                  │               │    urgency 1~4       │
                  │               │         ├──► Classifier (Haiku)
                  │               │         │         │   ──card──► UI 스트리밍
                  │               │    urgency 5       │            (WebSocket)
                  │               │         └──► ReAct Loop
                  │               │               (Sonnet)
                  │               │                  │
                  │               │             Classifier (Haiku)
                  │               │                  │   ──card──► UI 스트리밍
                  │               │                  │
                  │          (전체 완료)              │
                  │               │                  │
                  │               └──► Summarizer ───────header──► UI 확정
                  │                    (Sonnet)       │
                  │                                   │
              [PostgreSQL]                        React App
              classified_items                   Slack Bot
              briefings
```

---

## 시퀀스 다이어그램 — 복귀 브리핑 생성

```
Client   API GW  Orchestrator  Connectors  PQueue  UrgencyEng  Classifier  ReAct  Summarizer  DB
  │         │         │             │          │        │            │         │        │        │
  │─trigger►│         │            │          │        │            │         │        │        │
  │         │─start──►│            │          │        │            │         │        │        │
  │         │         │─spawn()────►│          │        │            │         │        │        │
  │         │         │            │─Gmail─►  │        │            │         │        │        │
  │         │         │            │─Slack─►  │        │            │         │        │        │ ← 병렬
  │         │         │            │─Cal───►  │        │            │         │        │        │
  │         │         │            │─Jira──►  │        │            │         │        │        │
  │         │         │            │          │        │            │         │        │        │
  │         │         │            │─item₁──►│        │            │         │        │        │
  │         │         │            │─item₂──►│─deq───►│            │         │        │        │
  │         │         │            │─item₃──►│        │─score(1~4)─►│        │        │        │
  │◄card₁───│◄────────│◄───────────│─────────│────────│◄─result────│         │        │        │
  │         │         │            │         │        │            │         │        │        │
  │         │         │            │─item₄──►│─deq───►│            │         │        │        │
  │         │         │            │         │        │─score(5)───────────►│        │        │
  │         │         │            │         │        │            │─result──►│        │        │
  │◄card₂───│◄────────│◄───────────│─────────│────────│────────────│─────────│        │        │
  │   ...   │         │            │         │        │            │         │        │        │
  │         │         │────────────────────────────────────────────────────────done──►│        │
  │         │         │            │         │        │            │         │        │─save──►│
  │◄header──│◄────────│◄───────────│─────────│────────│────────────│─────────│◄result─│        │
```

---

## 환경 변수 및 설정

```bash
# AI
ANTHROPIC_API_KEY=
CLASSIFIER_MODEL=claude-haiku-4-5-20251001
SUMMARIZER_MODEL=claude-sonnet-4-6
ACTION_MODEL=claude-sonnet-4-6

# 소스 연동
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
GOOGLE_CALENDAR_CLIENT_ID=
JIRA_API_TOKEN=
JIRA_BASE_URL=

# 인프라
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SECRET_KEY=

# 설정값
COLLECTION_LIMIT_PER_SOURCE=200
BRIEFING_TIMEOUT_SECONDS=60
CLASSIFIER_BATCH_SIZE=50
DEFAULT_ABSENCE_THRESHOLD_HOURS=8

# Urgency Engine 가중치
URGENCY_WEIGHT_TIME=0.35
URGENCY_WEIGHT_AUTHORITY=0.25
URGENCY_WEIGHT_FOLLOWUP=0.20
URGENCY_WEIGHT_KEYWORD=0.10
URGENCY_WEIGHT_SOURCE=0.10

# ReAct 설정
REACT_MAX_ITERATIONS=5
REACT_URGENCY_THRESHOLD=5       # 이 레벨 이상만 ReAct 실행
REACT_MODEL=claude-sonnet-4-6
```
