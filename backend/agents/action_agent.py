"""
Action Agent — on-demand 답장 초안 생성.
사용자가 카드에서 "초안 작성"을 클릭할 때 실행.
"""
from backend.models import WorkCard


async def draft_reply(card: WorkCard, user_context: str = "") -> str:
    """카드 내용을 바탕으로 답장 초안 생성. LLM Smart 티어."""
    ...
