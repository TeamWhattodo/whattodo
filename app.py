import os
import json
import tempfile
import streamlit as st
from datetime import datetime
from backend.agents.assistant_agent import (
    stream_agent, save_session, load_session, list_sessions, delete_session, rename_session
)

st.set_page_config(page_title="WhatToDo", layout="centered")

# ── 첫 실행 시 세션 초기화 ────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── 사이드바: 대화 목록 ──────────────────────────────────────────────
with st.sidebar:
    st.header("💬 대화 목록")

    if st.button("➕ 새 대화", use_container_width=True):
        save_session(st.session_state.session_id,
                     st.session_state.messages,
                     st.session_state.chat_history)
        new_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        st.session_state.session_id = new_id
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

    st.divider()

    if "editing_session" not in st.session_state:
        st.session_state.editing_session = None

    for s in list_sessions():
        is_current = s["id"] == st.session_state.session_id

        if st.session_state.editing_session == s["id"]:
            # ── 제목 편집 모드 ──
            new_name = st.text_input("", value=s["name"], key=f"rename_{s['id']}",
                                     label_visibility="collapsed")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 저장", key=f"save_{s['id']}", use_container_width=True):
                    rename_session(s["id"], new_name)
                    st.session_state.editing_session = None
                    st.rerun()
            with c2:
                if st.button("✖ 취소", key=f"cancel_{s['id']}", use_container_width=True):
                    st.session_state.editing_session = None
                    st.rerun()
        else:
            # ── 일반 모드 ──
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                label = f"**· {s['name']}**" if is_current else s["name"]
                if st.button(label, key=f"sess_{s['id']}", use_container_width=True):
                    if s["id"] != st.session_state.session_id:
                        save_session(st.session_state.session_id,
                                     st.session_state.messages,
                                     st.session_state.chat_history)
                        display, history = load_session(s["id"])
                        st.session_state.session_id = s["id"]
                        st.session_state.messages = display
                        st.session_state.chat_history = history
                        st.rerun()
            with col2:
                if st.button("✏️", key=f"edit_{s['id']}"):
                    st.session_state.editing_session = s["id"]
                    st.rerun()
            with col3:
                if st.button("🗑", key=f"del_{s['id']}"):
                    delete_session(s["id"])
                    if st.session_state.session_id == s["id"]:
                        st.session_state.session_id = "default"
                        st.session_state.messages = []
                        st.session_state.chat_history = []
                    st.rerun()

# ── 메인 화면 ─────────────────────────────────────────────────────────
st.title("WhatToDo")
st.caption("업무 보조 에이전트")


def _show_download_buttons(report: dict):
    col1, col2 = st.columns(2)
    file_prefix = report.get("report_type", "문서")
    
    with col1:
        if os.path.exists(report.get("xlsx_path", "")):
            with open(report["xlsx_path"], "rb") as f:
                st.download_button("📥 엑셀 다운로드", f, file_name=f"{file_prefix}.xlsx", key=report["xlsx_path"], use_container_width=True)
    with col2:
        if os.path.exists(report.get("pdf_path", "")):
            with open(report["pdf_path"], "rb") as f:
                st.download_button("📥 PDF 다운로드", f, file_name=f"{file_prefix}.pdf", key=report["pdf_path"], use_container_width=True)


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
                    if event["tool"] in ["process_expense_report", "write_report"]:
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
    save_session(st.session_state.session_id,
                 st.session_state.messages,
                 st.session_state.chat_history)
