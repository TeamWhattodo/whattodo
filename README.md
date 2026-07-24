# WhatToDo

휴가 다녀온 다음 날, 쌓인 이메일·슬랙·Jira를 어디서부터 봐야 할지 막막했던 경험 있으신가요?

**WhatToDo**는 AI 에이전트가 여러 업무 채널을 대신 훑어보고,  
"지금 당장 이것부터 처리하세요"를 정리해서 보여주는 서비스입니다.

---

## 이런 문제를 해결합니다

```
❌ 지금                         ✅ WhatToDo 사용 후
───────────────────────────     ───────────────────────────
출근 → 이메일 47통              출근 → 앱 열기 (30초)
    → 슬랙 213개 멘션                → 긴급 3건만 상단 표시
    → Jira 알림 8건                  → 나머지는 자동 분류
    → 뭐부터 봐야 하지...?           → 오전 안에 처리 완료
```

---

## 주요 기능

**복귀 브리핑** — 부재 기간 동안 쌓인 항목을 긴급도 순으로 정리해 카드로 보여줍니다.

**스마트 우선순위** — 저장된 deadline과 현재 시각을 비교해 긴급도를 실시간 계산합니다. AI의 주관적 판단이 아닌 정량 지표 기반입니다.

**답장 초안 작성** — 메일·슬랙 항목을 선택하면 AI가 맥락에 맞는 초안을 생성합니다.

**일정 관리** — Google Calendar 이벤트 조회 및 생성.

**경비 정산** — 영수증 이미지를 업로드하면 정산서(엑셀·PDF)를 자동 생성합니다.

**사내 규정 검색** — 규정집을 RAG로 검색해 즉시 답변합니다.

---

## 기술 스택

| 레이어 | 기술 |
|---|---|
| 프론트엔드 | React 19 + Vite (nginx) |
| 백엔드 | FastAPI + LangGraph Supervisor + ReAct |
| AI 에이전트 | LangGraph `create_react_agent` · SubAgent @tool 패턴 |
| 외부 소스 | Gmail · Google Calendar · Slack · Jira · Notion |
| 데이터베이스 | PostgreSQL + pgvector (관계형 · 벡터 · 대화 이력 통합) |
| 백그라운드 수집 | APScheduler (FastAPI lifespan, 2~15분 주기) |
| 배포 | Docker Compose (db · backend · frontend 3-서비스) |

---

## 시작하기

### Docker Compose (권장)

```bash
cp .env.example .env
# .env에 필요한 API 키 입력
docker compose up --build
```

- `http://localhost` → React 앱
- `http://localhost:8000/docs` → FastAPI 문서

### 로컬 개발

#### 필요한 것

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- Node.js 18+
- PostgreSQL (pgvector 익스텐션 포함)

#### 1. 환경 변수 설정

```bash
cp .env.example .env
```

`.env`를 열어 사용할 서비스의 API 키를 입력합니다.

```bash
# 필수
OPENAI_API_KEY=

DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost/whattodo
JWT_SECRET=<32바이트 이상 랜덤 문자열>
JWT_EXPIRE_DAYS=7
COOKIE_SECURE=false   # HTTPS 배포 시 true

# Gmail · Google Calendar 사용 시
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=

# Slack 사용 시
SLACK_BOT_TOKEN=
SLACK_TEAM_ID=
SLACK_BOT_USER_ID=

# Jira 사용 시
JIRA_API_TOKEN=
JIRA_EMAIL=
JIRA_BASE_URL=           # 예: https://yourorg.atlassian.net

# Notion 사용 시
NOTION_API_TOKEN=
```

> `JWT_SECRET` 생성: `python -c "import secrets; print(secrets.token_hex(32))"`
>
> 전체 환경 변수 목록은 `.env.example`을 참고하세요.

#### 2. 백엔드 실행

```bash
uv sync
uv run uvicorn backend.main:app --reload
```

#### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` 에서 앱을 확인할 수 있습니다.

> 백엔드와 프론트엔드를 **동시에** 실행해야 합니다.

---

## 성능 평가

TheAgentCompany 방법론 기반 에이전트 평가 스크립트입니다.

```bash
# DB를 먼저 띄운 뒤 실행
docker compose up db -d

# 전체 시나리오 실행
uv run python -m eval.run_eval

# 특정 시나리오만 실행
uv run python -m eval.run_eval S1 S3 S6

# 모델 지정 실행
uv run python -m eval.run_eval --model gpt-4o-mini

# 모델 비교 (권장) — 정리 → 평가 → 차트 한방에
uv run python -m eval.compare

# 모델당 5회 평균 (신뢰도 높은 비교)
uv run python -m eval.compare --runs 5

# 비교 차트 생성
uv run python -m eval.visualize
```

결과는 `eval/results/eval_YYYYMMDD_HHMMSS.json`, 차트는 `eval/charts/`에 저장됩니다.

| 지표 | 설명 |
|---|---|
| **Success Rate** | 모든 체크포인트 통과 비율 |
| **Partial Score** | `0.5 × (획득점수/전체점수) + 0.5 × 완전완료여부` |
| **Tool Call Accuracy** | 올바른 툴 호출 여부 |
| **Hallucination Rate** | LLM-Judge 할루시네이션 판정 비율 |

> `eval/results/`는 `.gitignore` 처리 — 결과 파일은 로컬에만 저장됩니다.

---

## 문서

| 문서 | 내용 |
|---|---|
| [docs/PLANNING.md](docs/PLANNING.md) | 서비스 기획, 기능 명세, 사용자 시나리오, 로드맵 |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | AI 에이전트 파이프라인 상세 흐름 |
| [docs/SPEC.md](docs/SPEC.md) | 기술 스택, API 목록, 디렉토리 구조, 전체 환경 변수 |
| [docs/whattodo_presentation.md](docs/whattodo_presentation.md) | 프로젝트 발표 자료 (아키텍처 진화, RAG 실험, 성능 평가) |
