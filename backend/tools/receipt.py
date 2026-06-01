import openai
import json
import logging

from backend.config import settings


def parse_receipt_from_text(text: str | list[str]) -> list[dict]:
    """
    추출된 영수증 텍스트 → ReceiptItem[] 반환.
    """
    texts = [text] if isinstance(text, str) else text
    combined = "\n\n---\n\n".join(texts)

    prompt = f"""아래 영수증 텍스트에서 정보를 추출해 JSON 배열로만 반환하라. 다른 텍스트 없이 JSON만.

[
  {{
    "date": "YYYY-MM-DD",
    "merchant": "가맹점명",
    "amount": 금액(정수, 원),
    "category": "출장비 | 숙박비 | 유류비 | 식비 | 기타",
    "memo": "메모 또는 null"
  }}
]

영수증 텍스트:
{combined}"""

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    content = (response.choices[0].message.content or "").strip()
    if content.startswith("```json"):
        content = content[7:-3].strip()
    elif content.startswith("```"):
        content = content[3:-3].strip()

    try:
        return json.loads(content)
    except (json.JSONDecodeError, IndexError) as e:
        logging.debug(f"parse_receipt_from_text 오류: {e}")
        return []
