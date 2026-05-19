"""
업무 문서 업로드 페이지 — n8n의 문서 업로드 Form Trigger 노드 대응.

맞춤법 검사·요약이 필요한 문서를 업로드하면
업무 벡터 스토어에 저장하고 에이전트가 검색 가능하게 한다.
"""
import streamlit as st

from backend.agents.agent import WorkAssistantAgent
from backend.services.vector_store import get_store
from backend.tools.spell_check import check_spelling

st.set_page_config(page_title="업무 문서 업로드", layout="centered")
st.title("업무 문서 업로드")
st.caption("맞춤법 검사, 요약이 필요한 문서를 업로드합니다.")

if "agent" not in st.session_state:
    st.session_state["agent"] = WorkAssistantAgent()

tab_upload, tab_spell = st.tabs(["문서 업로드", "맞춤법 검사"])

# ── 문서 업로드 탭 ────────────────────────────────────────────────────────────
with tab_upload:
    with st.form("doc_upload_form"):
        tag = st.text_input("태그/분류", placeholder="예: 기획서, 보고서, 회의록")
        uploaded = st.file_uploader("파일 선택", type=["txt", "pdf", "docx"])
        submitted = st.form_submit_button("업로드 및 저장", type="primary")

    if submitted:
        if uploaded is None:
            st.error("파일을 첨부해주세요.")
        else:
            with st.spinner("저장 중..."):
                text = _extract_text(uploaded)
                if text:
                    store = get_store("work")
                    store.insert(text, metadata={"tag": tag, "filename": uploaded.name})
                    st.success(f"'{uploaded.name}' 저장 완료 — 에이전트가 검색 가능합니다.")

# ── 맞춤법 검사 탭 ────────────────────────────────────────────────────────────
with tab_spell:
    text_input = st.text_area("검사할 텍스트 입력", height=200,
                              placeholder="맞춤법을 검사할 텍스트를 입력하세요.")
    if st.button("맞춤법 검사", type="primary"):
        if not text_input.strip():
            st.warning("텍스트를 입력해주세요.")
        else:
            with st.spinner("검사 중..."):
                result = check_spelling(text_input)
            if result.get("error"):
                st.error(result["error"])
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("원본")
                    st.text(result["original"])
                with col2:
                    st.subheader("교정")
                    st.text(result["corrected"])

st.divider()
store = get_store("work")
st.caption(f"현재 업무 스토어: {len(store)}개 문서 청크 저장됨")


def _extract_text(file) -> str:
    if file.name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    elif file.name.endswith(".pdf"):
        st.warning("PDF 파싱은 Phase 2에서 지원됩니다.")
        return ""
    elif file.name.endswith(".docx"):
        st.warning("Word 파싱은 Phase 2에서 지원됩니다.")
        return ""
    return ""
