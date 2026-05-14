# WhatToDo

여러 업무 채널(이메일·슬랙·캘린더)에 흩어진 알림과 태스크를 AI 에이전트가 자동 수집·분류·우선순위화해, **"지금 무엇을 해야 하는가"를 매일 제시**하고 **"오늘 무엇을 했는가"를 결산**해주는 AI 업무 인텔리전스 서비스.

---

## 문서

| 문서 | 내용 |
|---|---|
| [docs/PLANNING.md](docs/PLANNING.md) | 서비스 기획, 기능 명세, 로드맵, 팀 일정 |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | 에이전트 파이프라인 상세 워크플로우 |
| [docs/SPEC.md](docs/SPEC.md) | 기술 스택, API, 디렉토리 구조, 환경 변수 |

---

## 팀 구성 — 1인 1에이전트

| # | 담당 | 브랜치 | 핵심 파일 |
|---|---|---|---|
| 1 | Orchestrator | `feat/orchestrator` | `backend/main.py`, `routers/`, `db/` |
| 2 | Gmail Connector | `feat/gmail-connector` | `connectors/gmail.py`, `routers/auth.py` |
| 3 | Slack + Calendar Connector | `feat/slack-calendar-connector` | `connectors/slack.py`, `connectors/calendar.py` |
| 4 | Urgency Engine | `feat/urgency-engine` | `agents/urgency_engine.py` |
| 5 | Classifier + Summarizer | `feat/classifier-summarizer` | `agents/classifier.py`, `agents/summarizer.py` |
| 6 | Frontend Widget | `feat/briefing-widget` | `frontend/src/` |

> **Week 1 우선순위**: 담당 #1이 주도해 `WorkCard` / `BriefingHeader` 스키마를 전원 합의 후 확정.  
> 확정 전까지 담당 #6은 mock 데이터로 UI 개발을 시작할 수 없다.

---

## 기술 스택

```
Backend   FastAPI + Uvicorn
DB        TinyDB (JSON 파일, 서버 불필요)
Queue     heapq (Python 내장)
Scheduler APScheduler
AI        Anthropic SDK (Claude Haiku / Sonnet)
Frontend  React + Vite
OAuth     httpx + authlib
```

---

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)

### 백엔드 설정

```bash
# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 필수 값 입력 (아래 환경 변수 섹션 참고)

# 개발 서버 실행
uv run uvicorn backend.main:app --reload
```

서버 실행 후 `http://localhost:8000/health` 응답 확인.

### 프론트엔드 설정

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` 에서 위젯 확인.

---

## 디렉토리 구조

```
whattodo/
├── backend/
│   ├── main.py                  # FastAPI 앱 진입점
│   ├── routers/
│   │   ├── briefing.py          # 브리핑 WebSocket + REST  (#1)
│   │   ├── items.py             # 항목 상태 변경           (#1)
│   │   ├── summary.py           # 결산 API                 (#1)
│   │   └── auth.py              # OAuth 인증               (#2, #3)
│   ├── agents/
│   │   ├── orchestrator.py      # 파이프라인 제어          (#1)
│   │   ├── urgency_engine.py    # 정량 5-신호 계산         (#4)
│   │   ├── classifier.py        # Haiku: 액션 타입 + 요약  (#5)
│   │   └── summarizer.py        # Sonnet: 브리핑 헤더      (#5)
│   ├── connectors/
│   │   ├── base.py              # 커넥터 추상 클래스       (#1)
│   │   ├── gmail.py             # Gmail API                (#2)
│   │   ├── slack.py             # Slack API                (#3)
│   │   └── calendar.py          # Google Calendar API      (#3)
│   ├── db/
│   │   ├── store.py             # TinyDB 래퍼              (#1)
│   │   └── data/                # *.json 데이터 파일
│   ├── scheduler.py             # APScheduler 크론         (#1)
│   └── config.py                # 환경 변수 (pydantic-settings)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BriefingWidget.tsx
│   │   │   ├── WorkCard.tsx
│   │   │   ├── HeaderCard.tsx
│   │   │   └── ContactPanel.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   └── vite.config.ts
└── docs/
```

---

## WebSocket 메시지 스키마 ⚠️ Week 1 확정 필수

백엔드(#2~#5)와 프론트엔드(#6)가 공유하는 인터페이스.  
이 스키마가 확정되어야 #6이 mock 데이터로 독립 개발을 시작할 수 있다.

```typescript
// 분류 완료 즉시 카드 1건씩 스트리밍
interface WorkCard {
  id: string
  source: "gmail" | "slack" | "calendar"
  summary: string
  urgency_level: 1 | 2 | 3 | 4 | 5
  urgency_breakdown: { T: number; A: number; F: number; K: number; S: number }
  action_type: "reply" | "approve" | "review" | "fyi" | "none"
  from_person: string
  received_at: string        // ISO 8601
  estimated_minutes: number
  due_at: string | null
  status: "pending" | "done" | "snoozed"
}

// 전체 완료 후 1회 전송
interface BriefingHeader {
  briefing_id: string
  absence_days: number
  total: number
  urgent: number
  estimated_minutes: number
  contacts_needed: { person: string; reason: string; channel: string }[]
  summary_text: string
}

type WSMessage =
  | { type: "card";   data: WorkCard }
  | { type: "header"; data: BriefingHeader }
  | { type: "error";  message: string }
```

---

## 환경 변수

`.env.example`을 복사해 `.env`를 만들고 아래 값을 채운다.

```bash
# AI (필수)
ANTHROPIC_API_KEY=

# Gmail OAuth
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=

# Slack
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

# Google Calendar
GOOGLE_CALENDAR_CLIENT_ID=
GOOGLE_CALENDAR_CLIENT_SECRET=

# 앱
SECRET_KEY=                        # 임의 랜덤 문자열
FRONTEND_ORIGIN=http://localhost:5173

# 모델 (기본값 사용 권장)
CLASSIFIER_MODEL=claude-haiku-4-5-20251001
SUMMARIZER_MODEL=claude-sonnet-4-6
```

전체 환경 변수 목록은 [docs/SPEC.md](docs/SPEC.md#8-환경-변수) 참고.

---

## 브랜치 & PR 규칙

```
main        배포 가능 상태만. 금요일 주 1회 dev → main 병합
  └ dev     주간 통합 브랜치. PR은 dev로만 올린다
      ├ feat/orchestrator
      ├ feat/gmail-connector
      ├ feat/slack-calendar-connector
      ├ feat/urgency-engine
      ├ feat/classifier-summarizer
      └ feat/briefing-widget
```

**커밋 컨벤션**

```
feat:   새 기능
fix:    버그 수정
chore:  빌드·설정·의존성
docs:   문서
test:   테스트
```

**PR 체크리스트**

- [ ] `dev` 브랜치 기준으로 생성
- [ ] 로컬에서 `uv run pytest` 통과
- [ ] 변경된 스키마가 있다면 이 README의 스키마 섹션도 함께 수정

---

## MVP 4주 체크포인트

| 주차 | 완료 기준 |
|---|---|
| Week 1 | 스키마 확정, Gmail OAuth 로그인 성공, `GET /health` 응답, React 앱 로컬 실행 |
| Week 2 | Gmail 수집 → Urgency Engine 점수 출력 → WebSocket `WorkCard` 1건 전송 확인 |
| Week 3 | Slack·Calendar 포함 전체 파이프라인 E2E, 위젯에 카드 실시간 스트리밍 |
| Week 4 | 체크 완료 인터랙션, 에러 폴백, 브리핑 헤더 표시, 데모 시나리오 통과 |
