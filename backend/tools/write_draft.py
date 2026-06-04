from backend.agents.llm_client import complete
from backend.tools.storage import get_item_by_id

DRAFT_SYSTEM = """
당신은 전문 비서입니다. 주어진 맥락을 바탕으로 이메일 또는 메시지 초안을 작성하세요.
간결하고 정중하게 작성하며, 한국어로 출력하세요.
"""


def write_draft(user_id: int, item_id: str, tone: str = "formal") -> dict:
    """
    item_id로 WorkItem 조회 후 답장 초안을 생성한다.
    tone: formal | casual
    """
    item = get_item_by_id(item_id, user_id=user_id) or {}
    prompt = f"""
항목: {item.get('summary', item.get('raw_content', item_id))}
발신자: {item.get('from_person', '알 수 없음')}
톤: {'공식적' if tone == 'formal' else '캐주얼'}

위 내용에 대한 답변 초안을 작성해주세요.
"""
    try:
        draft = complete(prompt, tier="smart", system=DRAFT_SYSTEM)
        return {"item_id": item_id, "draft": draft}
    except Exception as e:
        return {"item_id": item_id, "draft": "", "error": str(e)}


if __name__ == "__main__":
    result = write_draft("email_001", tone="formal")
    print(result["draft"])
