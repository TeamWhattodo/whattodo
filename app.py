"""WhatToDo — 메인 진입점. 혼합형 레이아웃: 메인(카드) + 사이드바(채팅)."""
import streamlit as st

from backend.agents.agent import WorkAssistantAgent

st.set_page_config(page_title="WhatToDo", layout="wide", initial_sidebar_state="expanded")

if "agent" not in st.session_state:
    st.session_state["agent"] = WorkAssistantAgent()
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

agent: WorkAssistantAgent = st.session_state["agent"]

# ── 사이드바: 채팅 ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("업무 도우미")

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("무엇을 도와드릴까요?"):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("..."):
                response = agent.chat(prompt)
            st.markdown(response)
        st.session_state["chat_history"].append({"role": "assistant", "content": response})

# ── 메인: 브리핑 카드 ─────────────────────────────────────────────────────────
st.title("WhatToDo")

absence_days = st.number_input("부재 일수", min_value=1, max_value=30, value=3)

if st.button("브리핑 시작", type="primary"):
    with st.spinner("분석 중..."):
        result = agent.run_briefing(user_id="demo", absence_days=absence_days)
        st.session_state["briefing"] = result

if "briefing" in st.session_state:
    result = st.session_state["briefing"]
    h = result.header
    col1, col2, col3 = st.columns(3)
    col1.metric("총 항목", h.total)
    col2.metric("긴급", h.urgent)
    col3.metric("예상 소요", f"{h.estimated_minutes}분")

    st.divider()

    for card in result.cards:
        urgency_color = {5: "🔴", 4: "🟠", 3: "🟡", 2: "🟢", 1: "⚪"}.get(card.urgency_level, "⚪")
        with st.expander(f"{urgency_color} [{card.source.upper()}] {card.summary}", expanded=card.urgency_level >= 4):
            st.write(f"**보낸 사람:** {card.from_person}")
            st.write(f"**액션:** {card.action_type}")
            if card.due_at:
                st.write(f"**마감:** {card.due_at.strftime('%Y-%m-%d %H:%M')}")
