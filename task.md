# 사내 규정 문서 다중 포맷(HWP, DOCX) 지원 작업 내역

- [x] **Phase 1: 백엔드 환경 설정 및 파싱 패키지 추가**
  - [x] `pyproject.toml` (또는 `requirements.txt`)에 `docx2txt`, `pyhwp`, `olefile` 패키지 추가
  - [x] 도커 컨테이너(backend) 재빌드 또는 패키지 설치 확인

- [x] **Phase 2: 문서 파싱 로직 고도화 (Backend)**
  - [x] `backend/scripts/ingest_policy.py` 내에 `SUPPORTED_LOADERS` 확장
  - [x] `.docx` 파싱을 위한 `Docx2txtLoader` (Langchain) 연동
  - [x] `.hwp` 파싱을 위한 커스텀 텍스트 추출 로직(`olefile` 및 `zlib` 활용 등) 구현 및 `Document` 포맷 변환
  - [x] `backend/routers/chat.py` 의 문서 업로드 엔드포인트(`.pdf` 확장자 제한 해제) 수정

- [x] **Phase 3: 프론트엔드 업로드 UI 수정 (Frontend)**
  - [x] `SettingsModal.jsx` 내 파일 `<input accept="...">` 속성에 `.hwp`, `.docx`, `.doc` 추가
  - [x] 사용자 안내 문구 수정 (예: "사내 규정 문서(PDF, 워드, 한글)를 업로드하면...")

- [ ] **Phase 4: 전체 통합 테스트 및 검증**
  - [ ] HWP 파일 업로드 및 DB `policy_embeddings` 청크 삽입 검증
  - [ ] DOCX 파일 업로드 및 DB `policy_embeddings` 청크 삽입 검증
  - [ ] 채팅 창에서 RAG 쿼리 시 HWP/DOCX 내용이 올바르게 검색되어 반환되는지 확인
