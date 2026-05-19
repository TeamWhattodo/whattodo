"""
규정집 등록/업데이트 페이지 — n8n의 규정집 Form Trigger 노드 대응.

PDF/Word 파일을 업로드하면 텍스트를 추출해 규정집 벡터 스토어에 저장한다.
"""
import streamlit as st

from backend.tools.policy import load_policy_document
from backend.services.vector_store import get_store

st.set_page_config(page_title="규정집 관리", layout="centered")
st.title("규정집 등록/업데이트")
st.caption("회사 내규, 정산 기준 등 규정 문서를 등록합니다. PDF 또는 텍스트 파일을 업로드해 주세요.")

with st.form("policy_form"):
    doc_name = st.text_input("문서 이름", placeholder="예: 출장비 정산 기준 v2.3")
    uploaded = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"])
    submitted = st.form_submit_button("등록", type="primary")

if submitted:
    if not doc_name:
        st.error("문서 이름을 입력해주세요.")
    elif uploaded is None:
        st.error("파일을 첨부해주세요.")
    else:
        with st.spinner("처리 중..."):
            text = _extract_text(uploaded)
            chunk_count = load_policy_document(
                text,
                metadata={"doc_name": doc_name, "filename": uploaded.name},
            )
        st.success(f"'{doc_name}' 등록 완료 — {chunk_count}개 청크 저장됨")

st.divider()
store = get_store("rules")
st.caption(f"현재 규정집 스토어: {len(store)}개 청크 저장됨")


def _extract_text(file) -> str:
    """파일 타입에 따라 텍스트 추출."""
    if file.name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    elif file.name.endswith(".pdf"):
        # TODO: Phase 2 — pdfplumber 또는 pypdf 설치 후 구현
        st.warning("PDF 파싱은 Phase 2에서 지원됩니다. 텍스트 파일을 사용해주세요.")
        return ""
    elif file.name.endswith(".docx"):
        # TODO: Phase 2 — python-docx 설치 후 구현
        st.warning("Word 파싱은 Phase 2에서 지원됩니다. 텍스트 파일을 사용해주세요.")
        return ""
    return ""
