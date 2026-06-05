# OAuth 및 사용자 인증 고도화 작업 내역

- [x] **Phase 1: 설정 및 암호화 모듈 구현**
  - [x] `.env` 파일에 `jwt_refresh_secret` 및 `OAUTH_ENCRYPTION_KEY` 키 추가 (사용자 로컬 환경 안내)
  - [x] `backend/config.py`에 신규 환경변수 로드 추가
  - [x] `backend/utils/encryption.py` 생성 (토큰 암/복호화 로직 구현)

- [x] **Phase 2: 앱 자체 인증 시스템 개편 (Refresh Token)**
  - [x] `backend/auth/models.py` 내 `User` 모델에 `access_token`, `refresh_token` 컬럼 추가
  - [x] `backend/auth/security.py`에 Refresh Token 생성/해독 함수 구현
  - [x] `backend/auth/deps.py` 쿠키 이름 변경 (`token` -> `access_token`, `refresh_token`)
  - [x] `backend/auth/router.py`의 `login`, `register`, `logout` API 수정 (두 개의 쿠키 처리 및 DB 저장)
  - [x] `backend/auth/router.py`에 `/refresh` 엔드포인트 신규 구현

- [x] **Phase 3: 다중 사용자 외부 연동 토큰 관리**
  - [x] `backend/db/orm_models.py` 내 `OAuthTokenORM` 모델에 `user_id` 추가 및 PK 변경
  - [x] DB 마이그레이션 안내 (또는 컨테이너 재생성 안내)

- [x] **Phase 4: Final API Integration Check 및 디버깅**
  - [x] 프론트엔드/백엔드 통합 인증 버그(Cookie/Axios) 해결
  - [x] 임베딩 상태 실시간 동기화 개선 (폴링 완료 후 목록 갱신)
  - [x] UI 레이아웃, 문구 및 모달창 개선
  - [x] WSL2 환경에서의 핫 리로딩(HMR) 지원 설정 (Vite Polling 적용)
  - [x] 외부 토큰 암호화 적용 및 로드 시 복호화 로직 통합 적용
  - [x] 로그인 시 연동 상태(`connected`)를 내려주기 위한 로직 업데이트
  - [x] 연동 해제 API (`DELETE /auth/integrations/{source}`) 구현

- [ ] **Phase 5: 테스트 및 검증**
  - [ ] 로그인 시 `users` DB 토큰 저장 확인
  - [ ] 만료 시 `/refresh` 동작 확인
  - [ ] 연동 토큰 암호화 상태 확인 및 조회/해제 테스트
