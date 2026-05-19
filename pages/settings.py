"""
설정 페이지 — n8n의 자리비움 상태 확인(IF) + 로그인 트리거(Webhook) 노드 대응.

자리비움 모드 토글, 부재 메시지 설정, 데이터 수집 수동 트리거.
"""
from datetime import datetime

import streamlit as st

from backend.services.absence import (
    is_working,
    set_absence,
    set_working,
    get_away_message,
)
from backend.tools.fetch import fetch_messages
from backend.services.vector_store import get_store

st.set_page_config(page_title="설정", layout="centered")
st.title("설정")

# ── 자리비움 관리 ─────────────────────────────────────────────────────────────
st.subheader("자리비움 관리")
st.caption("자리비움 활성화 시 수신 메일에 자동으로 답장합니다.")

current_status = is_working()
status_label = "근무 중" if current_status else "자리비움"
st.info(f"현재 상태: **{status_label}**")

col1, col2 = st.columns(2)
with col1:
    if st.button("자리비움 설정", disabled=not current_status, use_container_width=True):
        st.session_state["show_absence_form"] = True

with col2:
    if st.button("복귀 처리", disabled=current_status, use_container_width=True, type="primary"):
        set_working()
        st.success("복귀 처리 완료")
        st.rerun()

if st.session_state.get("show_absence_form"):
    with st.form("absence_form"):
        away_msg = st.text_area(
            "부재 메시지",
            value="현재 자리를 비우고 있습니다. 복귀 후 연락드리겠습니다.",
        )
        return_date = st.date_input("복귀 예정일")
        return_time = st.time_input("복귀 예정 시각")
        confirmed = st.form_submit_button("자리비움 활성화", type="primary")

    if confirmed:
        return_at = datetime.combine(return_date, return_time)
        set_absence(away_msg, return_at=return_at)
        st.session_state["show_absence_form"] = False
        st.success("자리비움 모드가 활성화되었습니다.")
        st.rerun()

if not current_status:
    st.text_area("자동 답장 메시지 미리보기", value=get_away_message(), disabled=True)

st.divider()

# ── 데이터 수집 수동 트리거 ── n8n 로그인 트리거 대응 ──────────────────────────
st.subheader("데이터 수집")
st.caption("로그인 시 자동 수집 또는 수동으로 트리거합니다.")

days = st.slider("수집 기간 (일)", min_value=1, max_value=30, value=3)

if st.button("지금 수집 실행", type="primary"):
    store = get_store("work")
    total = 0
    with st.spinner("Slack, Jira, Gmail에서 수집 중..."):
        for source in ["gmail", "slack", "jira"]:
            items = fetch_messages(source, since_days=days)
            for item in items:
                content = f"[{item.source.upper()}] {item.from_name}: {item.subject}\n{item.body_snippet}"
                store.insert(content, metadata={"source": item.source, "raw_id": item.raw_id})
            total += len(items)
    st.success(f"수집 완료 — {total}건 → 업무 스토어 저장됨")

st.divider()

# ── 스토어 현황 ───────────────────────────────────────────────────────────────
st.subheader("스토어 현황")
col_r, col_w = st.columns(2)
col_r.metric("규정집 스토어", f"{len(get_store('rules'))}개 청크")
col_w.metric("업무 스토어", f"{len(get_store('work'))}개 청크")

if st.button("스토어 초기화", type="secondary"):
    get_store("rules").clear()
    get_store("work").clear()
    st.warning("모든 스토어가 초기화되었습니다.")
    st.rerun()
