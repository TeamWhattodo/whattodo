import base64
import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".csv",
    ".pdf",
    ".xlsx",
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
}


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 형식: {ext}")

    if ext in {".txt", ".md"}:
        return _read_plain(path)
    if ext == ".csv":
        return _read_csv(path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".xlsx":
        return _read_xlsx(path)
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return _read_image(path)

    raise ValueError(f"처리 불가: {ext}")


def _read_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_csv(path: Path) -> str:
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        rows = ["\t".join(row) for row in reader]
    return "\n".join(rows)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ImportError("pypdf 필요: pip install pypdf") from e

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages)

    # 텍스트 레이어 없음(스캔 PDF) → 페이지 렌더 후 Vision OCR
    if len(text.strip()) < 10:
        text = _ocr_pdf(path)
    return text


def _ocr_pdf(path: Path) -> str:
    """스캔 PDF: 페이지를 이미지로 렌더 → Vision OCR."""
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ImportError("PyMuPDF 필요: pip install pymupdf") from e

    logger.info("스캔 PDF 감지 → Vision OCR 진행: %s", path.name)
    doc = fitz.open(str(path))
    parts: list[str] = []
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            parts.append(_vision_extract(png_bytes, "image/png"))
    finally:
        doc.close()
    return "\n".join(parts)


def _read_xlsx(path: Path) -> str:
    try:
        import openpyxl
    except ImportError as e:
        raise ImportError("openpyxl 필요: pip install openpyxl") from e

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    parts: list[str] = []
    for sheet in wb.worksheets:
        parts.append(f"[시트: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            parts.append("\t".join(cells))
    wb.close()
    return "\n".join(parts)


def _read_image(path: Path) -> str:
    ext_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = ext_map.get(path.suffix.lower(), "image/jpeg")

    with path.open("rb") as f:
        image_bytes = f.read()

    return _vision_extract(image_bytes, media_type)


def _vision_extract(image_bytes: bytes, media_type: str = "image/png") -> str:
    """이미지 bytes → OpenAI Vision OCR 텍스트."""
    try:
        import openai
    except ImportError as e:
        raise ImportError("openai 필요: pip install openai") from e

    from backend.config import settings

    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}"
                        },
                    },
                    {
                        "type": "text",
                        "text": "이 이미지에서 텍스트를 모두 추출해라. 텍스트만 반환하고 다른 설명은 하지 마라.",
                    },
                ],
            }
        ],
        max_tokens=4096,
    )
    return response.choices[0].message.content or ""
