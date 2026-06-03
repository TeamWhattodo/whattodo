# 사내 규정 문서 폴더

이 폴더에 PDF 파일을 넣으면 서버 시작 시 자동으로 pgvector에 임베딩됩니다.

## 동작 방식

1. 서버 시작 → `docs/policy/` 폴더의 `.pdf` 파일 스캔
2. `.ingested.json` 마커 확인 → 미등록 파일만 임베딩
3. 임베딩 완료 후 `.ingested.json`에 기록 → 다음 시작 시 스킵

## 주의사항

- `.ingested.json`은 로컬 전용 (`.gitignore` 처리됨)
- DB 초기화 후 재임베딩이 필요하면 `.ingested.json` 삭제 후 서버 재시작
- pgvector 미설치 환경(일반 PostgreSQL)에서는 임베딩 기능 비활성화
