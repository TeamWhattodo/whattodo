import os
from datetime import datetime
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Malgun", "C:/Windows/Fonts/malgun.ttf"))
pdfmetrics.registerFont(TTFont("Malgun-Bold", "C:/Windows/Fonts/malgunbd.ttf"))


OUTPUT_DIR = "outputs"


def build_expense_report(items: list[dict], report_type: str = "출장비") -> dict:
    """
    ReceiptItem[] → 엑셀 + PDF 생성 후 ExpenseReport dict 반환
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    total     = sum(i["amount"] for i in items)

    xlsx_path = _write_xlsx(items, total, report_type, report_id)
    pdf_path  = _write_pdf(items, total, report_type, report_id)

    return {
        "id":           report_id,
        "created_at":   datetime.now().isoformat(),
        "report_type":  report_type,
        "items":        items,
        "total_amount": total,
        "xlsx_path":    xlsx_path,
        "pdf_path":     pdf_path,
    }


def _write_xlsx(items, total, report_type, report_id) -> str:
    path = f"{OUTPUT_DIR}/{report_id}.xlsx"
    wb   = Workbook()
    ws   = wb.active
    ws.title = report_type

    ws.append(["날짜", "가맹점", "금액(원)", "항목", "메모"])

    for item in items:
        ws.append([
            item["date"],
            item["merchant"],
            item["amount"],
            item["category"],
            item.get("memo", ""),
        ])

    ws.append(["", "합계", total, "", ""])

    wb.save(path)
    return path


def _write_pdf(items, total, report_type, report_id) -> str:
    path = f"{OUTPUT_DIR}/{report_id}.pdf"
    c    = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    c.setFont("Malgun-Bold", 16)
    c.drawString(50, h - 60, f"{report_type} 정산서")

    c.setFont("Malgun", 10)
    c.drawString(50, h - 90, f"작성일: {datetime.now().strftime('%Y-%m-%d')}")

    y = h - 130
    c.setFont("Malgun-Bold", 10)
    c.drawString(50,  y, "날짜")
    c.drawString(130, y, "가맹점")
    c.drawString(280, y, "금액")
    c.drawString(360, y, "항목")

    y -= 20
    c.setFont("Malgun", 10)
    for item in items:
        c.drawString(50,  y, item["date"])
        c.drawString(130, y, item["merchant"])
        c.drawString(280, y, f"{item['amount']:,}원")
        c.drawString(360, y, item["category"])
        y -= 18

    y -= 10
    c.setFont("Malgun-Bold", 10)
    c.drawString(130, y, "합계")
    c.drawString(280, y, f"{total:,}원")

    c.save()
    return path


if __name__ == "__main__":
    test_items = [
        {"date": "2026-05-12", "merchant": "GS칼텍스", "amount": 85000,
         "category": "유류비", "memo": "출장 이동"},
        {"date": "2026-05-12", "merchant": "롯데호텔", "amount": 42000,
         "category": "식비", "memo": "거래처 식사"},
    ]
    report = build_expense_report(test_items, "출장비")
    print(f"총액: {report['total_amount']:,}원")
    print(f"xlsx: {report['xlsx_path']}")
    print(f"pdf:  {report['pdf_path']}")
