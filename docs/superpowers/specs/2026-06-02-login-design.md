# 로그인 기능 설계 (앱 레벨 인증)

작성일: 2026-06-02
브랜치: `login`

## 1. 목표

앱 레벨 사용자 인증 도입. 자체 계정(아이디 + 비밀번호) 기반 셀프 회원가입,
JWT httpOnly 쿠키 세션, 대화 세션의 사용자별 분리.

## 2. 결정 사항

| 항목 | 결정 |
|---|---|
| 인증 방식 | 자체 계정 — username + password |
| 회원가입 | 셀프 회원가입 (가입 페이지) |
| 계정 저장소 | PostgreSQL |
| 세션 유지 | JWT + httpOnly 쿠키 |
| 데이터 분리 범위 | 대화 세션만 사용자별. Google OAuth 연동은 당분간 단일 공유 유지 |
| 로그인 식별자 | username (이메일 아님) |
| 스택 | SQLAlchemy(async) + passlib(bcrypt) + PyJWT (백엔드), react-router-dom (프론트) |

비포함(YAGNI): refresh 토큰, 비밀번호 재설정, 이메일 인증, 사용자별 Google OAuth, Alembic 마이그레이션.

## 3. 아키텍처 / 모듈 구성

```
backend/
  db/database.py        # async engine + session factory, 기동 시 create_all
  auth/
    models.py           # User ORM
    schemas.py          # Pydantic: RegisterReq, LoginReq, UserOut
    security.py         # bcrypt 해싱·검증, JWT 발급·디코드
    deps.py             # get_current_user (쿠키 JWT → User), 미인증 401
    router.py           # /api/auth/register, /login, /logout, /me
  routers/chat.py       # 기존 → Depends(get_current_user) 보호, user.id로 세션 스코프
  config.py             # + database_url, jwt_secret, jwt_expire_days
  main.py               # auth.router 등록, startup에 create_all

frontend/src/
  api/auth.js           # register/login/logout/me — fetch credentials:'include'
  context/AuthContext.jsx
  components/
    LoginPage.jsx
    RegisterPage.jsx
    ProtectedRoute.jsx
  App.jsx               # 라우터 + AuthProvider, 헤더 로그아웃 버튼
```

## 4. 데이터 모델 / 세션 스코프

### users 테이블 (Postgres)
```
id            SERIAL PRIMARY KEY
username      VARCHAR UNIQUE NOT NULL
password_hash VARCHAR NOT NULL
created_at    TIMESTAMP DEFAULT now()
```

### 대화 세션 사용자별 분리
현재: `data/sessions/<session_id>.json` (전역 공유).
변경:
- 파일 네임스페이스: `data/sessions/<user_id>/<session_id>.json`
- `sessions.py`의 `save_session / load_session / list_sessions / delete_session / rename_session`에 `user_id` 인자 추가
- `chat.py`가 `current_user.id`를 전달
- LangGraph MemorySaver thread_id = `f"{user_id}:{session_id}"` — 사용자 간 메모리 격리

세션 본문은 파일 유지(Postgres엔 user 테이블만). 변경 최소화. 추후 필요 시 세션 DB 이전.

## 5. API 엔드포인트

| 메서드 | 경로 | 동작 | 성공 응답 |
|---|---|---|---|
| POST | `/api/auth/register` | username 중복 체크 → bcrypt 해싱 → insert → JWT 쿠키 set(자동 로그인) | 201 + UserOut |
| POST | `/api/auth/login` | username 조회 → 비번 검증 → JWT 쿠키 set | 200 + UserOut |
| POST | `/api/auth/logout` | 쿠키 만료 삭제 | 200 |
| GET | `/api/auth/me` | 쿠키 JWT 디코드 → 현재 user | 200 + UserOut / 401 |

보호 대상: `chat.py`의 `/chat`, `/sessions`, `/sessions/{id}` (GET/PATCH/DELETE) 전부 `Depends(get_current_user)`.

## 6. 데이터 흐름

- 가입/로그인 → 서버: `Set-Cookie: token=<JWT>; HttpOnly; SameSite=Lax; Path=/` (prod는 `Secure` 추가)
- 이후 요청: 브라우저가 쿠키 자동 첨부(프론트 `credentials:'include'`) → `get_current_user`가 JWT 디코드 → `user_id` → 세션 쿼리 스코프 적용
- 로그아웃 → `Set-Cookie` 만료로 쿠키 삭제
- 앱 진입 → `AuthContext`가 `/api/auth/me` 호출 → 200이면 로그인 상태, 401이면 `/login` 리다이렉트

### JWT
- 알고리즘 HS256
- payload: `{ "sub": <user_id>, "exp": <만료> }`
- 만료: `jwt_expire_days` (기본 7일)
- refresh 토큰 없음 — 만료 시 재로그인

## 7. 프론트엔드 (React)

- `react-router-dom` 도입 (현재 단일 App.jsx). 라우트: `/login`, `/register`, `/`(앱, 보호)
- `AuthContext`: user 상태 보관. 앱 로드 시 `/api/auth/me`로 세션 확인.
- `ProtectedRoute`: 미인증 → `/login` 리다이렉트.
- 로그인/가입 성공 → user 상태 갱신 → `/`로 이동.
- 모든 API 호출 `credentials:'include'`.
- 헤더 로그아웃 버튼 → `/api/auth/logout` → user 비우고 `/login`.

## 8. 보안

- 비번 해싱: bcrypt (passlib). 평문 저장·로깅 금지.
- 검증: 비번 최소 8자, username 3~30자 영숫자 (Pydantic).
- JWT 시크릿: `.env`의 `jwt_secret`. 미설정 시 기동 거부 — 약한 기본값 금지.
- 쿠키: `HttpOnly` + `SameSite=Lax` + `Secure`(prod). 자바스크립트 토큰 접근 차단.
- CORS: `allow_origins=["http://localhost:5173"]` 유지, `allow_credentials=True` 필수.

## 9. 에러 처리

| 상황 | 응답 |
|---|---|
| username 중복 가입 | 409 |
| 로그인 실패(없는 id / 틀린 비번) | 401, 메시지 동일("아이디 또는 비밀번호가 올바르지 않습니다") — 계정 존재 노출 방지 |
| 미인증 보호 라우트 | 401 |
| 만료 토큰 | 401 → 프론트 `/login` 리다이렉트 |

## 10. 테스트 (pytest)

- 가입 성공 / username 중복 409
- 로그인 성공·쿠키 발급 / 틀린 비번 401
- `/me`: 쿠키 유 → 200, 무 → 401
- 보호 라우트 미인증 401
- 세션 격리: userA 세션을 userB가 조회·삭제 불가
- 비번 해시 저장 확인(평문 아님)

## 11. 의존성 추가

- 백엔드: `sqlalchemy[asyncio]`, `asyncpg`, `passlib[bcrypt]`, `pyjwt`
- 프론트: `react-router-dom`
- 설정: `.env`에 `database_url`, `jwt_secret`, `jwt_expire_days`
