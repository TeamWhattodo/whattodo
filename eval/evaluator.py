import json
from langchain_core.messages import AIMessage, ToolMessage


def get_all_tool_calls(state: dict) -> set[str]:
    """에이전트 메시지에서 호출된 툴 이름 전체 수집."""
    called = set()
    for msg in state.get("messages", []):
        # AIMessage의 tool_calls
        for tc in getattr(msg, "tool_calls", None) or []:
            if isinstance(tc, dict):
                called.add(tc.get("name", ""))
        # ToolMessage의 name (툴 결과)
        name = getattr(msg, "name", None)
        if name:
            called.add(name)
    return called


def check_tool_call(state: dict, tool_names: list[str]) -> tuple[bool, str]:
    called = get_all_tool_calls(state)
    for name in tool_names:
        if name in called:
            return True, f"호출 확인: {name}"
    return False, f"미호출 (확인된 툴: {', '.join(called) or '없음'})"


def check_response_contains(response_text: str, keywords: list[str], min_match: int = 1) -> tuple[bool, str]:
    matched = [kw for kw in keywords if kw in response_text]
    passed = len(matched) >= min_match
    return passed, f"매칭 키워드: {matched or '없음'}"


def llm_judge(response_text: str, criterion: str, query: str) -> tuple[bool, str]:
    import datetime
    from backend.agents.llm_client import get_llm
    from langchain_core.messages import HumanMessage

    today = datetime.date.today().strftime("%Y-%m-%d")
    prompt = f"""다음 기준으로 AI 에이전트의 응답을 평가하세요.

오늘 날짜: {today} (이 날짜 기준으로 판단하세요. 2026년은 현재 연도입니다.)
사용자 요청: {query}
평가 기준: {criterion}
에이전트 응답:
{response_text[:2000]}

JSON만 반환하세요: {{"pass": true 또는 false, "reason": "한 줄 이유"}}"""

    try:
        raw = get_llm("fast").invoke([HumanMessage(content=prompt)]).content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return bool(data.get("pass")), data.get("reason", "")
    except Exception as e:
        return False, f"판정 오류: {e}"


def check_file_exists(state: dict, field: str) -> tuple[bool, str]:
    import os
    # state results 확인
    for val in state.get("results", {}).values():
        if isinstance(val, dict):
            path = val.get(field, "")
            if path and os.path.exists(path):
                return True, f"파일 생성됨: {path}"
    # ToolMessage content JSON 파싱
    for msg in state.get("messages", []):
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    # 최상위 레벨 확인
                    path = data.get(field, "")
                    if path and os.path.exists(path):
                        return True, f"파일 생성됨: {path}"
                    # files 배열 내부 확인 (supervisor 아키텍처)
                    for file_item in data.get("files", []):
                        if isinstance(file_item, dict):
                            path = file_item.get(field, "")
                            if path and os.path.exists(path):
                                return True, f"파일 생성됨: {path}"
            except Exception:
                pass
    return False, "파일 미생성"


def extract_response(state: dict) -> str:
    """state에서 평가용 전체 응답 텍스트 추출.

    Supervisor 아키텍처에서 실제 데이터는 ToolMessage에 있고,
    마지막 AIMessage는 요약 문장만 있으므로 둘을 합쳐서 반환한다.
    """
    parts = []

    for msg in state.get("messages", []):
        cls = msg.__class__.__name__
        content = msg.content if isinstance(msg.content, str) else ""

        # ToolMessage: fetch_agent/search_agent 등 서브에이전트 실제 결과
        if cls == "ToolMessage" and content.strip():
            # JSON 결과면 text 필드만 추출
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    text = data.get("text", "")
                    if text:
                        parts.append(text)
                    else:
                        parts.append(content)
                else:
                    parts.append(content)
            except Exception:
                parts.append(content)

        # AIMessage (tool_calls 없는 것): Supervisor 최종 요약
        elif cls == "AIMessage" and not getattr(msg, "tool_calls", []) and content.strip():
            parts.append(content)

    if parts:
        return "\n\n".join(parts)

    # 레거시 results fallback
    for key in ("briefing", "report", "action", "search", "chat"):
        r = state.get("results", {}).get(key)
        if not r:
            continue
        if isinstance(r, dict):
            return r.get("text", "")
        return str(r)
    return ""
