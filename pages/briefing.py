"""복귀 브리핑 페이지 — 담당 #6."""
import streamlit as st

from backend.agents.briefing_agent import run_simple

st.set_page_config(page_title="복귀 브리핑", layout="wide")
st.title("복귀 브리핑")

absence_days = st.number_input("부재 일수", min_value=1, max_value=30, value=3)

if st.button("브리핑 시작", type="primary"):
    with st.spinner("분석 중..."):
        st.session_state["report"] = run_simple(user_id="demo", absence_days=absence_days)

if "report" in st.session_state:
    st.markdown(st.session_state["report"])
