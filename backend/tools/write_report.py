import json
from backend.agents.llm_client import complete

BRIEFING_SYSTEM = """
주어진 업무 항목 데이터를 한국어 브리핑 보고서로 작성하라.
긴급도 순으로 정리하고, 각 항목의 핵심 액션을 한 줄로 요약하라.
"""

REPORT_SYSTEM = """
주어진 데이터를 한국어 업무 보고서로 작성하라. 간결하고 명확하게.
"""


def write_report(report_type: str, data: dict | list) -> dict:
    """
    report_type: "briefing" | "daily_summary" | "kpi_weekly" | "billing"
    data: 보고서에 포함할 항목들
    반환: {"report_type": ..., "content": str}
    """
    system = BRIEFING_SYSTEM if report_type == "briefing" else REPORT_SYSTEM
    prompt = f"[{report_type}] 보고서를 작성해줘:\n{json.dumps(data, ensure_ascii=False, default=str)}"
    try:
        content = complete(prompt, tier="smart", system=system)
        return {"report_type": report_type, "content": content}
    except Exception as e:
        return {"report_type": report_type, "content": "", "error": str(e)}


if __name__ == "__main__":
    test = [{"source": "gmail", "summary": "계약서 서명 요청", "urgency_level": 5}]
    result = write_report("briefing", test)
    print(result["content"])
