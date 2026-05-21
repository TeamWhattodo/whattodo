import openai
import base64
import json
import os
from dotenv import load_dotenv

load_dotenv()


def parse_receipt(image_path: str) -> list[dict]:
    """
    영수증 이미지 → ReceiptItem[] 반환.
    OpenAI Vision API 사용.
    """
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = image_path.split(".")[-1].lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png"}.get(ext, "image/jpeg")

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt_text = """이 영수증에서 정보를 추출해 JSON 배열로만 반환하라. 다른 텍스트 없이 JSON만.

[
  {
    "date": "YYYY-MM-DD",
    "merchant": "가맹점명",
    "amount": 금액(정수, 원),
    "category": "출장비 | 유류비 | 식비 | 기타",
    "memo": "메모 또는 null"
  }
]"""

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt_text,
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                },
            ],
        }],
    )

    content = response.choices[0].message.content.strip()
    if content.startswith("```json"):
        content = content[7:-3].strip()
    elif content.startswith("```"):
        content = content[3:-3].strip()

    try:
        return json.loads(content)
    except (json.JSONDecodeError, IndexError) as e:
        print(f"영수증 파싱 오류: {e}")
        print(f"API 응답: {content}")
        return []


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    items = parse_receipt(path)
    for item in items:
        print(f"{item['date']} | {item['merchant']} | {item['amount']}원 | {item['category']}")
