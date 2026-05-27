import json
from backend.agents.llm_client import complete

SPELLCHECK_SYSTEM = """
당신은 한국어 맞춤법 및 교정 전문가입니다.
주어진 텍스트의 맞춤법, 띄어쓰기, 어색한 문맥을 교정하고 그 결과를 반드시 JSON 형식으로만 반환하세요.
다른 텍스트나 설명은 절대 포함하지 마세요.

반환 포맷:
{
  "original": "원본 텍스트",
  "corrected": "교정된 텍스트",
  "reasons": ["수정 사유 1", "수정 사유 2"]
}
"""

def check_spelling(text: str) -> dict:
    """
    입력받은 텍스트의 맞춤법을 교정하여 반환한다.
    """
    if not text or not text.strip():
        return {"original": text, "corrected": text, "reasons": []}
        
    prompt = f"교정할 텍스트:\n{text}"
    
    try:
        raw = complete(prompt, tier="smart", system=SPELLCHECK_SYSTEM)
        parsed = json.loads(raw.strip())
        return parsed
    except Exception as e:
        # 에러 발생 시 원본 텍스트 그대로 반환하며 에러 메시지 포함
        return {
            "original": text,
            "corrected": text,
            "reasons": [],
            "error": str(e)
        }

if __name__ == "__main__":
    test_text = "어제 회의에서 대표님이 내일까지 보고서를 재출하라고 하셧다."
    result = check_spelling(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
