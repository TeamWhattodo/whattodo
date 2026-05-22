import os
import json
import tempfile
import streamlit as st
from backend.agents.assistant_agent import stream_agent

st.set_page_config(page_title="WhatToDo", layout="centered")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("WhatToDo")
st.caption("업무 보조 에이전트")


def _show_download_buttons(report: dict):
    col1, col2 = st.columns(2)
    with col1:
        if os.path.exists(report.get("xlsx_path", "")):
            with open(report["xlsx_path"], "rb") as f:
                st.download_button("📥 엑셀 다운로드", f, file_name="정산서.xlsx", use_container_width=True)
    with col2:
        if os.path.exists(report.get("pdf_path", "")):
            with open(report["pdf_path"], "rb") as f:
                st.download_button("📥 PDF 다운로드", f, file_name="정산서.pdf", use_container_width=True)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("report"):
            _show_download_buttons(msg["report"])

if st.button("📋 브리핑 시작", use_container_width=True):
    st.session_state.pending_query = "긴급한 업무 정리해줘"

chat_input = st.chat_input("업무 명령을 입력하세요",
                            accept_file="multiple",
                            file_type=["jpg", "jpeg", "png"])

query          = None
uploaded_files = []

if chat_input:
    query          = chat_input.text or "첨부한 영수증으로 정산서를 작성해줘"
    uploaded_files = chat_input.files or []
elif st.session_state.get("pending_query"):
    query = st.session_state.pop("pending_query")

if query:
    tmp_paths = []
    for uf in uploaded_files:
        suffix = os.path.splitext(uf.name)[-1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uf.read())
            tmp_paths.append(tmp.name)

    if tmp_paths:
        display_query = f"{query} (파일 {len(tmp_paths)}개 첨부)"
        paths_str     = "\n".join(f"- {p}" for p in tmp_paths)
        agent_query   = f"{query}\n\n첨부된 파일:\n{paths_str}"
    else:
        display_query = query
        agent_query   = query

    with st.chat_message("user"):
        st.markdown(display_query)
    st.session_state.messages.append({"role": "user", "content": display_query})

    response_text = ""
    report_data   = None
    with st.chat_message("assistant"):
        with st.status("에이전트 실행 중...", expanded=True) as status:
            for event in stream_agent(agent_query, st.session_state.chat_history):
                if event["type"] == "tool_call":
                    st.write(f"🔧 `{event['tool']}` 호출 중...")
                elif event["type"] == "tool_result":
                    st.write(f"✅ `{event['tool']}` 완료")
                    if event["tool"] == "process_expense_report":
                        try:
                            report_data = json.loads(event["content"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                elif event["type"] == "done":
                    response_text = event["text"]
                    st.session_state.chat_history = event["history"]
            status.update(label="완료", state="complete", expanded=False)
        st.markdown(response_text)
        if report_data:
            _show_download_buttons(report_data)

    for p in tmp_paths:
        try:
            os.unlink(p)
        except OSError:
            pass

    st.session_state.messages.append({
        "role":    "assistant",
        "content": response_text,
        "report":  report_data,
    })
