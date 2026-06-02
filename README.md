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

**체크리스트 위젯** — 처리하면 체크, 완료 항목은 아래로 내려갑니다. 할 일 목록이 눈에 보이게 줄어드는 걸 확인할 수 있습니다.

**스마트 우선순위** — "마감이 얼마나 남았는지", "누가 보냈는지", "같은 사람이 몇 번 연락했는지"를 조합해 긴급도를 계산합니다. AI의 주관적 판단이 아닌 정량 지표 기반입니다.

**일간 결산** *(Phase 2)* — 퇴근 전 "오늘 7건 완료, 3건 내일로 이월" 요약을 자동으로 만들어줍니다.

**주간 KPI** *(Phase 3)* — 완료율, 평균 응답 시간, 채널별 업무 부하를 주간 단위로 리포트합니다.

---

## 화면 미리보기

```
┌─────────────────────────────────────┐
│ WhatToDo  5월 13일 복귀 브리핑      │
│ 4일 부재 · 268건 수신 · 예상 85분   │
│ ──────────────────────────────────  │
│ 🔴 지금 당장  3건                   │
│                                     │
│ ☐ [✉] 김대표 → 계약서 서명 요청    │
│      CEO · 마감 초과 · ~10분        │
│      [초안 작성]  [열기]            │
│                                     │
│ ☐ [J] PROJ-402 배포 승인 대기      │
│      마감 5/12 초과 · ~5분          │
│                                     │
│ ☐ [S] 박팀장 DM 3건 — 예산 승인    │
│      30분 전 · ~10분                │
│                                     │
│ ─── 오늘 안에  4건 ───────── ▼ ───  │
│ ─── 이번 주    9건 ───────── ▼ ───  │
│ ─── FYI      180건 ───────── ▼ ───  │
└─────────────────────────────────────┘
```

---

## 시작하기

### 필요한 것

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- Node.js 18+

### 백엔드

```bash
uv sync
npm install            # Slack MCP 서버 설치
cp .env.example .env   # API 키와 OAuth 정보 입력
uv run uvicorn backend.main:app --reload
```

`http://localhost:8000/health` 에서 응답이 오면 준비 완료.

### 프론트엔드 (Streamlit)

```bash
uv run streamlit run app.py
```

`http://localhost:8501` 에서 위젯을 확인할 수 있습니다.

### 최소 필요 환경 변수

```bash
ANTHROPIC_API_KEY=    # Anthropic 콘솔에서 발급
GMAIL_CLIENT_ID=      # Google Cloud Console
GMAIL_CLIENT_SECRET=
SLACK_BOT_TOKEN=      # Slack App 설정
SECRET_KEY=           # 임의 랜덤 문자열
```

전체 환경 변수 목록은 [docs/SPEC.md](docs/SPEC.md#8-환경-변수)를 참고하세요.

---

## 팀 협업

6명이 1인 1담당으로 병렬 개발합니다.

| # | 담당 | 브랜치 |
|---|---|---|
| 1 | Briefing Agent (tool_use 루프) | `feat/briefing-agent` |
| 2 | Gmail Fetch Tool | `feat/gmail-tool` |
| 3 | Slack + Calendar Fetch Tool | `feat/slack-calendar-tool` |
| 4 | Scoring Tool (긴급도 계산) | `feat/scoring-tool` |
| 5 | Classify + Storage Tool | `feat/classify-tool` |
| 6 | Streamlit UI | `feat/streamlit-ui` |

**PR은 `dev` 브랜치로만** 올립니다. `main` 병합은 금요일 주 1회.

> **Week 1에 꼭 해야 할 것**: 담당 #1이 주도해 `WorkCard` · `BriefingResult` Pydantic 모델을 전원 합의 후 확정합니다.  
> 모델이 확정되어야 담당 #6이 `mock_data.py`로 Streamlit UI 개발을 독립적으로 시작할 수 있습니다.

---

## 성능 평가

TheAgentCompany 방법론 기반 에이전트 평가 스크립트입니다.

```bash
# 전체 시나리오 실행 (12개)
uv run python -m eval.run_eval

# 특정 시나리오만 실행
uv run python -m eval.run_eval S1 S3 S6

# 모델 지정 실행
uv run python -m eval.run_eval --model gpt-4o
uv run python -m eval.run_eval --model gpt-4o-mini

# 결과 비교 그래프 생성 (eval/results/ 전체 자동 비교)
uv run python -m eval.visualize

# 특정 파일만 비교
uv run python -m eval.visualize eval/results/파일1.json eval/results/파일2.json
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
