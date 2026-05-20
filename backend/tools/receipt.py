import anthropic
import base64
import json
import os


def parse_receipt(image_path: str) -> list[dict]:
    """
    영수증 이미지 → ReceiptItem[] 반환.
    Anthropic Vision API 사용.
    """
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = image_path.split(".")[-1].lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png"}.get(ext, "image/jpeg")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_data},
                },
                {
                    "type": "text",
                    "text": """이 영수증에서 정보를 추출해 JSON 배열로만 반환하라. 다른 텍스트 없이 JSON만.

[
  {
    "date": "YYYY-MM-DD",
    "merchant": "가맹점명",
    "amount": 금액(정수, 원),
    "category": "출장비 | 유류비 | 식비 | 기타",
    "memo": "메모 또는 null"
  }
]""",
                },
            ],
        }],
    )

    try:
        return json.loads(response.content[0].text.strip())
    except Exception:
        return []


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    items = parse_receipt(path)
    for item in items:
        print(f"{item['date']} | {item['merchant']} | {item['amount']}원 | {item['category']}")
