import os
import json
import tempfile
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from backend.agents.graph import stream_graph_events, get_graph_state, resume_graph
from backend.tools.extract_text import extract_text
from backend.agents.sessions import (
    save_session, load_session, list_sessions, delete_session, rename_session,
)
from backend.google_auth import get_auth_url, handle_callback, is_authenticated

st.set_page_config(page_title="WhatToDo", layout="centered")


def _build_history(display_messages: list[dict]) -> list:
    """display 메시지에서 MemorySaver 주입용 BaseMessage 이력을 생성한다."""
    from langchain_core.messages import HumanMessage, AIMessage
    history = []
    for m in display_messages:
        if m["role"] == "user":
            history.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant" and m.get("content"):
            history.append(AIMessage(content=m["content"]))
    return history

# ── Google OAuth 콜백 처리 (URL에 ?code= 파라미터가 있을 때) ─────────
_params = st.query_params
if "code" in _params and not is_authenticated():
    try:
        handle_callback(_params["code"])
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Google 인증 실패: {e}")

# ── 첫 실행 시 세션 초기화 ─────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
    st.session_state.messages = []

# ── 사이드바: 대화 목록 ───────────────────────────────────────────────
with st.sidebar:
    # ── Google 연동 상태 ──
    st.header("🔗 Google 연동")
    if is_authenticated():
        st.success("Gmail · Calendar 연결됨")
        if st.button("Google 로그아웃 (초기화)", use_container_width=True):
            if os.path.exists("data/google_token.json"):
                os.remove("data/google_token.json")
            st.rerun()
    else:
        st.warning("Google 미연결")
        auth_url = get_auth_url()
        st.link_button("Google 계정 연결", auth_url, use_container_width=True)

    st.divider()
    st.header("💬 대화 목록")

    if st.button("➕ 새 대화", use_container_width=True):
        save_session(st.session_state.session_id, st.session_state.messages,
                     _build_history(st.session_state.messages))
        new_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        st.session_state.session_id = new_id
        st.session_state.messages = []
        st.rerun()

    st.divider()

    if "editing_session" not in st.session_state:
        st.session_state.editing_session = None

    for s in list_sessions():
        is_current = s["id"] == st.session_state.session_id

        if st.session_state.editing_session == s["id"]:
            new_name = st.text_input("", value=s["name"], key=f"rename_{s['id']}",
                                     label_visibility="collapsed")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 저장", key=f"save_{s['id']}", use_container_width=True):
                    rename_session(s["id"], new_name or s["name"])
                    st.session_state.editing_session = None
                    st.rerun()
            with c2:
                if st.button("✖ 취소", key=f"cancel_{s['id']}", use_container_width=True):
                    st.session_state.editing_session = None
                    st.rerun()
        else:
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                label = f"**· {s['name']}**" if is_current else s["name"]
                if st.button(label, key=f"sess_{s['id']}", use_container_width=True):
                    if s["id"] != st.session_state.session_id:
                        save_session(st.session_state.session_id,
                                     st.session_state.messages,
                                     _build_history(st.session_state.messages))
                        display, history = load_session(s["id"])
                        st.session_state.session_id = s["id"]
                        st.session_state.messages = display
                        st.session_state.loaded_history = history
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
                    st.rerun()

# ── 메인 화면 ──────────────────────────────────────────────────────────
st.title("WhatToDo")
st.caption("업무 보조 에이전트")


def _extract_response(state: dict) -> str:
    """Supervisor 응답(messages) 또는 레거시 results dict에서 텍스트를 추출한다."""
    # Supervisor: messages 마지막 AIMessage (tool_calls 없는 것)
    for msg in reversed(state.get("messages", [])):
        if msg.__class__.__name__ == "AIMessage" and not getattr(msg, "tool_calls", []):
            return msg.content
    # 레거시 fallback
    results = state.get("results", {})
    for key in ("action", "search", "report", "briefing", "chat"):
        r = results.get(key)
        if not r:
            continue
        if isinstance(r, dict):
            return r.get("text", json.dumps(r, ensure_ascii=False, default=str))
        return str(r)
    return state.get("error") or "처리가 완료되었습니다."


def _extract_reports(state: dict) -> list[dict]:
    """Supervisor ToolMessage 또는 레거시 results에서 파일 경로를 수집한다."""
    reports = []
    # MemorySaver thread는 이전 턴 메시지까지 누적되므로, 마지막 사용자 입력
    # (HumanMessage) 이후 메시지만 스캔해 이번 턴 결과만 수집한다.
    # (대화 기억엔 영향 없음 — 스캔 범위만 좁히는 로컬 처리)
    messages = state.get("messages", [])
    last_human = max(
        (i for i, m in enumerate(messages)
         if m.__class__.__name__ == "HumanMessage"),
        default=0,
    )
    # Supervisor: ToolMessage 결과에서 JSON 파싱
    for msg in messages[last_human:]:
        if msg.__class__.__name__ != "ToolMessage":
            continue
        try:
            data = json.loads(msg.content)
            if not isinstance(data, dict):
                continue
            # 새 형식: files 리스트
            for f in data.get("files", []):
                if isinstance(f, dict) and (f.get("xlsx_path") or f.get("pdf_path")):
                    reports.append(f)
            # 레거시: 직접 경로 필드
            if data.get("xlsx_path") or data.get("pdf_path"):
                reports.append(data)
        except Exception:
            pass
    # 레거시 fallback
    if not reports:
        results = state.get("results", {})
        for r in results.values():
            if not isinstance(r, dict):
                continue
            if r.get("xlsx_path") or r.get("pdf_path"):
                reports.append(r)
            if "reports" in r and isinstance(r["reports"], list):
                reports.extend(r["reports"])
    return reports


def _show_download_buttons(reports: list[dict], key_prefix: str = ""):
    report_type_map = {
        "briefing": "긴급 보고서",
        "daily_summary": "일일 보고서",
        "kpi_weekly": "주간 보고서",
        "monthly_summary": "월간 보고서",
        "billing": "경비 정산서"
    }
    
    for i, report in enumerate(reports):
        col1, col2 = st.columns(2)
        raw_type = report.get("report_type", f"문서_{i}")
        file_prefix = report_type_map.get(raw_type, raw_type)
        unique = f"{key_prefix}_{i}_{report.get('pdf_path', '')}_{report.get('xlsx_path', '')}"
        
        with col1:
            if os.path.exists(report.get("xlsx_path", "")):
                with open(report["xlsx_path"], "rb") as f:
                    st.download_button(f"📥 {file_prefix} (엑셀)", f, file_name=f"{file_prefix}.xlsx", key=f"xlsx_{unique}", use_container_width=True)
        with col2:
            if os.path.exists(report.get("pdf_path", "")):
                with open(report.get("pdf_path", ""), "rb") as f:
                    st.download_button(f"📥 {file_prefix} (PDF)", f, file_name=f"{file_prefix}.pdf", key=f"pdf_{unique}", use_container_width=True)


_TOOL_DISPLAY: dict[str, str] = {
    "extract_text":   "📄 첨부파일 분석 중",
    "fetch_agent":    "📥 데이터 수집 중",
    "briefing_agent": "📋 브리핑 작성 중",
    "report_agent":   "📝 리포트 작성 중",
    "search_agent":   "🔍 문서 검색 중",
    "action_agent":   "⚡ 액션 실행 중",
}


def _stream_and_render(
    agent_query: str,
    thread_id: str,
    history,
    text_placeholder,
    status_placeholder,
) -> str:
    """stream_graph_events를 소비하며 UI를 실시간 업데이트하고 최종 텍스트를 반환한다."""
    full_text = ""
    for event in stream_graph_events(agent_query, thread_id, history):
        kind = event["event"]
        name = event.get("name", "")
        meta = event.get("metadata", {})

        if kind == "on_tool_start" and name in _TOOL_DISPLAY:
            status_placeholder.info(f"🔄 {_TOOL_DISPLAY[name]}")

        elif kind == "on_tool_end" and name in _TOOL_DISPLAY:
            status_placeholder.success(f"✅ {name.replace('_agent', '')} 완료")

        elif kind == "on_chat_model_stream" and meta.get("langgraph_node") == "agent":
            chunk = event["data"].get("chunk")
            if chunk:
                token = chunk.content if isinstance(chunk.content, str) else ""
                if token:
                    full_text += token
                    text_placeholder.markdown(full_text + "▌")

    if full_text:
        text_placeholder.markdown(full_text)
    return full_text


messages = st.session_state.messages
for idx, msg in enumerate(messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        is_last = (idx == len(messages) - 1)
        if msg.get("reports") and is_last:
            _show_download_buttons(msg["reports"], key_prefix=f"hist_{idx}")


# ── HitL 대기 중: interrupt() 재개 처리 ───────────────────────────────
if st.session_state.get("hitl_pending"):
    interrupt_data = st.session_state.hitl_data
    st.warning(interrupt_data.get("message", "액션을 실행하시겠습니까?"))
    col1, col2 = st.columns(2)
    if col1.button("✅ 확인", key="hitl_confirm", use_container_width=True):
        with st.spinner("실행 중..."):
            state = resume_graph(st.session_state.session_id, "yes")
        st.session_state.hitl_pending = False
        response_text = _extract_response(state)
        report_data   = _extract_reports(state)
        st.session_state.messages.append({
            "role": "assistant", "content": response_text, "reports": report_data,
        })
        save_session(st.session_state.session_id, st.session_state.messages,
                     _build_history(st.session_state.messages))
        st.rerun()
    if col2.button("❌ 취소", key="hitl_cancel", use_container_width=True):
        with st.spinner("취소 중..."):
            state = resume_graph(st.session_state.session_id, "no")
        st.session_state.hitl_pending = False
        response_text = _extract_response(state)
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        save_session(st.session_state.session_id, st.session_state.messages,
                     _build_history(st.session_state.messages))
        st.rerun()
    st.stop()
# ─────────────────────────────────────────────────────────────────────


if st.button("📋 브리핑 시작", use_container_width=True):
    st.session_state.pending_query = "Gmail, Slack, Jira, Notion 업무 전체 정리해줘"

chat_input = st.chat_input("업무 명령을 입력하세요",
                            accept_file="multiple",
                            file_type=["jpg", "jpeg", "png", "pdf", "txt", "md"])

query          = None
uploaded_files = []

if chat_input:
    query          = chat_input.text or "요청 사항을 입력하세요"
    uploaded_files = chat_input.files or []
elif st.session_state.get("pending_query"):
    query = st.session_state.pop("pending_query")

if query:
    # 입력 즉시 표시 (파일 추출·에이전트 실행 전에 렌더 → 지연 체감 제거)
    display_query = f"{query} (파일 첨부 완료)" if uploaded_files else query
    with st.chat_message("user"):
        st.markdown(display_query)
    st.session_state.messages.append({"role": "user", "content": display_query})

    with st.chat_message("assistant"):
        text_box   = st.empty()
        status_box = st.empty()
        loaded_history = st.session_state.pop("loaded_history", None)

        extracted_texts = []
        for uf in uploaded_files:
            status_box.info(f"🔄 {_TOOL_DISPLAY['extract_text']}: {uf.name}")
            suffix = os.path.splitext(uf.name)[-1].lower() or ".bin"
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uf.read())
                    tmp_path = tmp.name
                text = extract_text(tmp_path)
                extracted_texts.append(f"--- {uf.name} 시작 ---\n{text}\n--- {uf.name} 끝 ---\n")
            except Exception as e:
                extracted_texts.append(f"[{uf.name} 읽기 실패: {e}]")
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        if extracted_texts:
            texts_str = "\n".join(extracted_texts)
            agent_query = query + f"\n\n첨부된 문서 내용:\n{texts_str}"
        else:
            agent_query = query

        full_text = _stream_and_render(
            agent_query, st.session_state.session_id, loaded_history,
            text_box, status_box,
        )
        status_box.empty()

        # interrupt 확인 (action_agent HitL)
        snapshot = get_graph_state(st.session_state.session_id)
        all_interrupts = [
            i for task in snapshot.tasks for i in getattr(task, "interrupts", ())
        ]
        if all_interrupts:
            idata = all_interrupts[0].value if hasattr(all_interrupts[0], "value") else all_interrupts[0]
            st.session_state.hitl_pending = True
            st.session_state.hitl_data    = idata
            save_session(st.session_state.session_id, st.session_state.messages,
                         _build_history(st.session_state.messages))
            st.rerun()

        # 스트리밍 텍스트가 없는 경우 state에서 추출 (fallback)
        if not full_text:
            full_text = _extract_response(snapshot.values)
            text_box.markdown(full_text)

        report_data = _extract_reports(snapshot.values)
        if report_data:
            _show_download_buttons(report_data, key_prefix="new")

    st.session_state.messages.append({
        "role":    "assistant",
        "content": full_text,
        "reports": report_data,
    })
    save_session(st.session_state.session_id, st.session_state.messages,
                     _build_history(st.session_state.messages))
    st.rerun()
