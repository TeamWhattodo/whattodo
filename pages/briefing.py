"""복귀 브리핑 페이지 — 담당 #6."""
import asyncio

import streamlit as st

from backend.config import settings

st.set_page_config(page_title="복귀 브리핑", layout="wide")
st.title("복귀 브리핑")

absence_days = st.number_input("부재 일수", min_value=1, max_value=30, value=1)

if st.button("브리핑 시작", type="primary"):
    with st.spinner("수집 중..."):
        if settings.use_mock_data:
            from backend.mock_data import get_mock_briefing
            result = get_mock_briefing()
        else:
            from backend.agents.briefing_agent import run
            result = asyncio.run(run(user_id="demo", absence_days=absence_days))
        st.session_state["briefing"] = result

if "briefing" not in st.session_state:
    st.stop()

# TODO: 브리핑 카드 UI 구현 (#6 담당)
result = st.session_state["briefing"]
st.json(result.model_dump())  # 임시: 원시 데이터 표시
