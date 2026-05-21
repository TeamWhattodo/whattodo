import streamlit as st
from backend.agents.assistant_agent import stream_agent

st.set_page_config(page_title="WhatToDo", layout="centered")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []    # LangChain Message 객체 리스트

st.title("WhatToDo")
st.caption("업무 보조 에이전트")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

col1, col2 = st.columns(2)
with col1:
    if st.button("📋 브리핑 시작", use_container_width=True):
        st.session_state.pending_query = "긴급한 업무 정리해줘"
with col2:
    uploaded = st.file_uploader("🧾 영수증 업로드", type=["jpg", "jpeg", "png"],
                                 label_visibility="collapsed")
    if uploaded:
        st.session_state.pending_query = f"__receipt__{uploaded.name}"
        st.session_state.uploaded_file = uploaded

query = st.chat_input("업무 명령을 입력하세요")
if not query and st.session_state.get("pending_query"):
    query = st.session_state.pop("pending_query")

if query:
    display_query = "영수증 업로드됨" if query.startswith("__receipt__") else query
    with st.chat_message("user"):
        st.markdown(display_query)
    st.session_state.messages.append({"role": "user", "content": display_query})

    response_text = ""
    with st.chat_message("assistant"):
        if query.startswith("__receipt__"):
            # ── 영수증 정산 경로 ─────────────────────────────────────────
            from backend.tools.receipt import parse_receipt
            from backend.tools.expense import build_expense_report
            import tempfile, os

            uploaded_file = st.session_state.pop("uploaded_file")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name

            items = parse_receipt(tmp_path)
            report = build_expense_report(items, "출장비")
            os.unlink(tmp_path)

            response_text = f"정산서 작성 완료 — 총 {report['total_amount']:,}원\n\n"
            for item in report["items"]:
                response_text += f"- {item['date']} | {item['merchant']} | {item['amount']:,}원\n"
            st.markdown(response_text)

            col1, col2 = st.columns(2)
            with col1:
                with open(report["xlsx_path"], "rb") as f:
                    st.download_button("📥 엑셀 다운로드", f, file_name="정산서.xlsx", use_container_width=True)
            with col2:
                with open(report["pdf_path"], "rb") as f:
                    st.download_button("📥 PDF 다운로드", f, file_name="정산서.pdf", use_container_width=True)

        else:
            # ── LangChain 에이전트 + tool 단계 표시 ──────────────────────
            with st.status("에이전트 실행 중...", expanded=True) as status:
                for event in stream_agent(query, st.session_state.chat_history):
                    if event["type"] == "tool_call":
                        st.write(f"🔧 `{event['tool']}` 호출 중...")
                    elif event["type"] == "tool_result":
                        st.write(f"✅ `{event['tool']}` 완료")
                    elif event["type"] == "done":
                        response_text = event["text"]
                        st.session_state.chat_history = event["history"]
                status.update(label="완료", state="complete", expanded=False)
            st.markdown(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})
